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


def _manifest_entry(manifest: dict, archive_path: str) -> dict:
    for entry in manifest['entries']:
        if entry['archive_path'] == archive_path:
            return entry
    raise AssertionError(f'missing manifest entry: {archive_path}')


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
    context.paths.ccbd_ipc_path.write_text('{"ipc_kind":"unix_socket","ipc_ref":"/tmp/repo/.ccb/ccbd/ccbd.sock"}\n', encoding='utf-8')
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
    assert any(entry['archive_path'] == 'project/.ccb/ccbd/ipc.json' for entry in manifest['entries'])
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


def test_export_diagnostic_bundle_collects_windows_runtime_binding_metadata(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-bundle-windows-bindings'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    context = CliContextBuilder().build(
        ParsedDoctorCommand(project=None, bundle=True),
        cwd=project_root,
        bootstrap_if_missing=False,
    )

    context.paths.ccbd_shutdown_report_path.parent.mkdir(parents=True, exist_ok=True)
    context.paths.ccbd_shutdown_report_path.write_text('{"runtime_states":"ok"}\n', encoding='utf-8')

    session_path = context.paths.ccb_dir / 'sessions' / 'demo.session.json'
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text('{"session":"demo"}\n', encoding='utf-8')

    runtime_root = context.paths.agent_provider_runtime_dir('demo', 'codex')
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / 'job.id').write_text('job-object-1\n', encoding='utf-8')
    (runtime_root / 'job-owner.pid').write_text('654\n', encoding='utf-8')
    (runtime_root / 'owner.pid').write_text('654\n', encoding='utf-8')
    (runtime_root / 'bridge.pid').write_text('4321\n', encoding='utf-8')

    context.paths.agent_runtime_path('demo').parent.mkdir(parents=True, exist_ok=True)
    context.paths.agent_runtime_path('demo').write_text(
        json.dumps(
            {
                'schema_version': 2,
                'record_type': 'agent_runtime',
                'agent_name': 'demo',
                'state': 'idle',
                'pid': 101,
                'started_at': '2026-04-21T00:00:00Z',
                'last_seen_at': '2026-04-21T00:00:01Z',
                'runtime_ref': 'psmux:%7',
                'session_ref': None,
                'session_file': str(session_path),
                'session_id': 'session-demo',
                'workspace_path': str(context.paths.workspace_path('demo')),
                'project_id': context.project.project_id,
                'backend_type': 'pane_backed',
                'queue_depth': 0,
                'socket_path': None,
                'health': 'healthy',
                'terminal_backend': 'psmux',
                'runtime_root': str(runtime_root),
                'runtime_pid': 4321,
                'job_id': 'job-object-1',
                'job_owner_pid': 654,
            }
        ) + '\n',
        encoding='utf-8',
    )

    summary = export_diagnostic_bundle(context, ParsedDoctorCommand(project=None, bundle=True))
    bundle_path = Path(summary.bundle_path)
    manifest = _read_tar_json(bundle_path, f'{summary.bundle_id}/manifest.json')
    doctor_payload = _read_tar_json(bundle_path, f'{summary.bundle_id}/generated/doctor.json')

    assert _manifest_entry(manifest, 'project/.ccb/ccbd/shutdown-report.json')['status'] == 'included'
    assert _manifest_entry(manifest, 'project/.ccb/agents/demo/provider-runtime/codex/job.id')['status'] == 'included'
    assert _manifest_entry(manifest, 'project/.ccb/agents/demo/provider-runtime/codex/job-owner.pid')['status'] == 'included'
    assert _manifest_entry(manifest, 'project/.ccb/agents/demo/provider-runtime/codex/owner.pid')['status'] == 'included'
    assert _manifest_entry(manifest, 'project/.ccb/agents/demo/provider-runtime/codex/bridge.pid')['status'] == 'included'
    assert _manifest_entry(manifest, 'project/.ccb/sessions/demo.session.json')['status'] == 'included'

    agent = doctor_payload['agents'][0]
    assert agent['runtime_pid'] == 4321
    assert agent['runtime_root'] == str(runtime_root)
    assert agent['session_file'] == str(session_path)
    assert agent['session_id'] == 'session-demo'
    assert agent['job_id'] == 'job-object-1'
    assert agent['job_owner_pid'] == 654
