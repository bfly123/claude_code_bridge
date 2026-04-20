from __future__ import annotations

import json
from pathlib import Path
import tarfile

from cli.context import CliContextBuilder
from cli.models import ParsedDoctorCommand
from cli.services.diagnostics import export_diagnostic_bundle


def _read_tar_json(bundle_path: Path, member_name: str) -> dict:
    with tarfile.open(bundle_path, 'r:gz') as archive:
        with archive.extractfile(member_name) as handle:
            assert handle is not None
            return json.loads(handle.read().decode('utf-8'))


def _archive_members(bundle_path: Path) -> list[str]:
    with tarfile.open(bundle_path, 'r:gz') as archive:
        return archive.getnames()


def test_export_diagnostic_bundle_collects_reports_and_log_tails(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-bundle'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    context = CliContextBuilder().build(
        ParsedDoctorCommand(project=None, bundle=True),
        cwd=project_root,
        bootstrap_if_missing=False,
    )

    context.paths.ccbd_dir.mkdir(parents=True, exist_ok=True)
    context.paths.ccbd_state_path.write_text('{"record_type":"ccbd_project_namespace_state"}\n', encoding='utf-8')
    context.paths.ccbd_start_policy_path.write_text('{"record_type":"ccbd_start_policy"}\n', encoding='utf-8')
    context.paths.ccbd_lifecycle_log_path.write_text('{"record_type":"ccbd_project_namespace_event"}\n', encoding='utf-8')
    heartbeat_path = context.paths.heartbeat_subject_path('job_progress', 'job_1')
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    heartbeat_path.write_text(
        '{"record_type":"heartbeat_state"}\n',
        encoding='utf-8',
    )
    context.paths.ccbd_startup_report_path.write_text('{"broken":false}\n', encoding='utf-8')
    context.paths.ccbd_dir.joinpath('ccbd.stdout.log').write_text('\n'.join(f'line {i}' for i in range(400)), encoding='utf-8')
    context.paths.agent_runtime_path('demo').parent.mkdir(parents=True, exist_ok=True)
    context.paths.agent_runtime_path('demo').write_text(
        json.dumps(
            {
                'schema_version': 2,
                'record_type': 'agent_runtime',
                'agent_name': 'demo',
                'state': 'idle',
                'pid': 101,
                'started_at': '2026-04-03T00:00:00Z',
                'last_seen_at': '2026-04-03T00:00:01Z',
                'runtime_ref': 'tmux:%1',
                'session_ref': None,
                'workspace_path': str(context.paths.workspace_path('demo')),
                'project_id': context.project.project_id,
                'backend_type': 'tmux',
                'queue_depth': 0,
                'socket_path': None,
                'health': 'healthy',
            }
        ) + '\n',
        encoding='utf-8',
    )

    summary = export_diagnostic_bundle(context, ParsedDoctorCommand(project=None, bundle=True))
    bundle_path = Path(summary.bundle_path)
    manifest = _read_tar_json(bundle_path, f'{summary.bundle_id}/manifest.json')

    assert bundle_path.exists()
    assert summary.file_count >= 4
    assert summary.truncated_count >= 1
    assert any(entry['archive_path'] == 'project/.ccb/ccbd/state.json' for entry in manifest['entries'])
    assert any(entry['archive_path'] == 'project/.ccb/ccbd/start-policy.json' for entry in manifest['entries'])
    assert any(entry['archive_path'] == 'project/.ccb/ccbd/lifecycle.jsonl' for entry in manifest['entries'])
    assert any(entry['archive_path'] == 'project/.ccb/ccbd/heartbeats/job_progress/job_1.json' for entry in manifest['entries'])
    assert any(entry['archive_path'] == 'project/.ccb/ccbd/startup-report.json' for entry in manifest['entries'])
    assert any(entry['archive_path'] == 'project/.ccb/ccbd/ccbd.stdout.log' for entry in manifest['entries'])
    assert any(entry['archive_path'] == 'project/.ccb/agents/demo/runtime.json' for entry in manifest['entries'])


def test_export_diagnostic_bundle_survives_corrupt_runtime_and_report_files(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-bundle-corrupt'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    context = CliContextBuilder().build(
        ParsedDoctorCommand(project=None, bundle=True),
        cwd=project_root,
        bootstrap_if_missing=False,
    )

    context.paths.ccbd_startup_report_path.parent.mkdir(parents=True, exist_ok=True)
    context.paths.ccbd_startup_report_path.write_text('{this is not json}\n', encoding='utf-8')
    context.paths.agent_runtime_path('demo').parent.mkdir(parents=True, exist_ok=True)
    context.paths.agent_runtime_path('demo').write_text('{this is also not json}\n', encoding='utf-8')

    summary = export_diagnostic_bundle(context, ParsedDoctorCommand(project=None, bundle=True))
    bundle_path = Path(summary.bundle_path)
    manifest = _read_tar_json(bundle_path, f'{summary.bundle_id}/manifest.json')

    assert bundle_path.exists()
    assert any(
        entry['archive_path'] == 'project/.ccb/ccbd/startup-report.json' and entry['status'] == 'included'
        for entry in manifest['entries']
    )
    assert any(
        entry['archive_path'] == 'project/.ccb/agents/demo/runtime.json' and entry['status'] == 'included'
        for entry in manifest['entries']
    )


def test_export_diagnostic_bundle_includes_provider_state_and_excludes_auth(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-bundle-provider-state'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    context = CliContextBuilder().build(
        ParsedDoctorCommand(project=None, bundle=True),
        cwd=project_root,
        bootstrap_if_missing=False,
    )

    provider_state_dir = context.paths.agent_provider_state_dir('demo', 'codex')
    session_log = provider_state_dir / 'home' / 'sessions' / '2026' / '04' / '19' / 'rollout-demo-session.jsonl'
    session_log.parent.mkdir(parents=True, exist_ok=True)
    session_log.write_text('{"type":"session_meta"}\n', encoding='utf-8')
    isolated_home = provider_state_dir / 'home'
    isolated_home.mkdir(parents=True, exist_ok=True)
    (isolated_home / 'config.toml').write_text('[model]\nname="gpt-5"\n', encoding='utf-8')
    (isolated_home / 'auth.json').write_text('{"OPENAI_API_KEY":"secret"}\n', encoding='utf-8')

    summary = export_diagnostic_bundle(context, ParsedDoctorCommand(project=None, bundle=True))
    bundle_path = Path(summary.bundle_path)
    manifest = _read_tar_json(bundle_path, f'{summary.bundle_id}/manifest.json')
    members = _archive_members(bundle_path)

    assert any(
        entry['archive_path'] == 'project/.ccb/agents/demo/provider-state/codex/home/sessions/2026/04/19/rollout-demo-session.jsonl'
        and entry['status'] == 'included'
        for entry in manifest['entries']
    )
    assert any(
        entry['archive_path'] == 'project/.ccb/agents/demo/provider-state/codex/home/config.toml'
        and entry['status'] == 'included'
        for entry in manifest['entries']
    )
    assert all(
        entry['archive_path'] != 'project/.ccb/agents/demo/provider-state/codex/home/auth.json'
        for entry in manifest['entries']
    )
    assert f'{summary.bundle_id}/project/.ccb/agents/demo/provider-state/codex/home/auth.json' not in members
