from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ccbd.lifecycle_report_store import CcbdStartupReportStore
from ccbd.models import CcbdStartupReport
from cli.context import CliContextBuilder
from cli.models import ParsedStartCommand
from cli.services.start import start_agents
from project.resolver import bootstrap_project


def test_start_agents_calls_ccbd_start_with_cli_flags(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-start-thin-client'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedStartCommand(project=None, agent_names=('demo',), restore=True, auto_permission=True)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    seen: dict[str, object] = {}

    class _FakeClient:
        def start(self, **kwargs):
            seen.update(kwargs)
            return {
                'project_root': str(project_root),
                'project_id': context.project.project_id,
                'started': ['demo'],
                'socket_path': str(context.paths.ccbd_socket_path),
                'cleanup_summaries': [],
            }

    monkeypatch.setattr(
        'cli.services.start.ensure_daemon_started',
        lambda context: SimpleNamespace(client=_FakeClient(), started=True),
    )

    summary = start_agents(context, command)

    assert seen == {
        'agent_names': ('demo',),
        'restore': True,
        'auto_permission': True,
    }
    assert summary.project_root == str(project_root)
    assert summary.project_id == context.project.project_id
    assert summary.started == ('demo',)
    assert summary.daemon_started is True
    assert summary.socket_path == str(context.paths.ccbd_socket_path)


def test_start_agents_parses_cleanup_summaries_from_ccbd_payload(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-start-cleanup'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedStartCommand(project=None, agent_names=(), restore=False, auto_permission=False)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    class _FakeClient:
        def start(self, **kwargs):
            del kwargs
            return {
                'project_root': str(project_root),
                'project_id': context.project.project_id,
                'started': ['demo'],
                'socket_path': str(context.paths.ccbd_socket_path),
                'cleanup_summaries': [
                    {
                        'socket_name': 'sock-a',
                        'owned_panes': ['%44'],
                        'active_panes': ['%44'],
                        'orphaned_panes': [],
                        'killed_panes': [],
                    },
                ],
            }

    monkeypatch.setattr(
        'cli.services.start.ensure_daemon_started',
        lambda context: SimpleNamespace(client=_FakeClient(), started=False),
    )

    summary = start_agents(context, command)

    assert summary.daemon_started is False
    assert len(summary.cleanup_summaries) == 1
    assert summary.cleanup_summaries[0].socket_name == 'sock-a'
    assert summary.cleanup_summaries[0].owned_panes == ('%44',)


def test_start_agents_updates_startup_report_with_daemon_started_flag(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-start-report'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedStartCommand(project=None, agent_names=('demo',), restore=False, auto_permission=False)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)
    CcbdStartupReportStore(context.paths).save(
        CcbdStartupReport(
            project_id=context.project.project_id,
            generated_at='2026-04-03T00:00:00Z',
            trigger='start_command',
            status='ok',
            requested_agents=('demo',),
            desired_agents=('demo',),
            restore_requested=False,
            auto_permission=False,
            daemon_generation=1,
            daemon_started=None,
            config_signature='sig-1',
            inspection={},
            restore_summary={},
            actions_taken=('launch_runtime:demo',),
            cleanup_summaries=(),
            agent_results=(),
            failure_reason=None,
        )
    )

    class _FakeClient:
        def start(self, **kwargs):
            del kwargs
            return {
                'project_root': str(project_root),
                'project_id': context.project.project_id,
                'started': ['demo'],
                'socket_path': str(context.paths.ccbd_socket_path),
                'cleanup_summaries': [],
            }

    monkeypatch.setattr(
        'cli.services.start.ensure_daemon_started',
        lambda context: SimpleNamespace(client=_FakeClient(), started=True),
    )

    start_agents(context, command)

    report = CcbdStartupReportStore(context.paths).load()
    assert report is not None
    assert report.daemon_started is True
