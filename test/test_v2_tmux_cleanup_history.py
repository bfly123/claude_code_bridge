from __future__ import annotations

from pathlib import Path

from ccbd.lifecycle_report_store import CcbdShutdownReportStore, CcbdStartupReportStore
from ccbd.models import CcbdShutdownReport, CcbdStartupReport
from ccbd.services.project_namespace_state import ProjectNamespaceEvent, ProjectNamespaceEventStore, ProjectNamespaceState, ProjectNamespaceStateStore
from cli.context import CliContextBuilder
from cli.models import ParsedDoctorCommand
from cli.services.doctor import doctor_summary
from cli.services.tmux_cleanup_history import TmuxCleanupEvent, TmuxCleanupHistoryStore
from cli.services.tmux_project_cleanup import ProjectTmuxCleanupSummary
from project.resolver import bootstrap_project
from storage.paths import PathLayout


def test_tmux_cleanup_history_store_loads_latest(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-history'
    project_root.mkdir()
    bootstrap_project(project_root)
    layout = PathLayout(project_root)
    store = TmuxCleanupHistoryStore(layout)

    store.append(
        TmuxCleanupEvent(
            event_kind='start',
            project_id='proj-1',
            occurred_at='2026-03-31T01:00:00Z',
            summaries=(
                ProjectTmuxCleanupSummary(
                    socket_name=None,
                    owned_panes=('%1', '%2'),
                    active_panes=('%1',),
                    orphaned_panes=('%2',),
                    killed_panes=('%2',),
                ),
            ),
        )
    )
    store.append(
        TmuxCleanupEvent(
            event_kind='kill',
            project_id='proj-1',
            occurred_at='2026-03-31T01:10:00Z',
            summaries=(
                ProjectTmuxCleanupSummary(
                    socket_name='sock-a',
                    owned_panes=('%9',),
                    active_panes=(),
                    orphaned_panes=('%9',),
                    killed_panes=('%9',),
                ),
            ),
        )
    )

    latest = store.load_latest()

    assert latest is not None
    assert latest.event_kind == 'kill'
    assert latest.summary_fields()['tmux_cleanup_total_killed'] == 1
    assert latest.summary_fields()['tmux_cleanup_sockets'] == ['sock-a']


def test_doctor_summary_includes_latest_tmux_cleanup_fields(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-doctor-history'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    context = CliContextBuilder().build(ParsedDoctorCommand(project=None), cwd=project_root, bootstrap_if_missing=False)

    TmuxCleanupHistoryStore(context.paths).append(
        TmuxCleanupEvent(
            event_kind='start',
            project_id=context.project.project_id,
            occurred_at='2026-03-31T01:20:00Z',
            summaries=(
                ProjectTmuxCleanupSummary(
                    socket_name=None,
                    owned_panes=('%1', '%2'),
                    active_panes=('%1',),
                    orphaned_panes=('%2',),
                    killed_panes=('%2',),
                ),
            ),
        )
    )

    payload = doctor_summary(context)

    assert payload['ccbd']['tmux_cleanup_last_kind'] == 'start'
    assert payload['ccbd']['tmux_cleanup_last_at'] == '2026-03-31T01:20:00Z'
    assert payload['ccbd']['tmux_cleanup_total_orphaned'] == 1
    assert payload['ccbd']['tmux_cleanup_total_killed'] == 1


def test_doctor_summary_includes_namespace_state_and_latest_event(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-doctor-namespace'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    context = CliContextBuilder().build(ParsedDoctorCommand(project=None), cwd=project_root, bootstrap_if_missing=False)

    ProjectNamespaceStateStore(context.paths).save(
        ProjectNamespaceState(
            project_id=context.project.project_id,
            namespace_epoch=4,
            tmux_socket_path=str(context.paths.ccbd_tmux_socket_path),
            tmux_session_name=context.paths.ccbd_tmux_session_name,
            layout_version=1,
            ui_attachable=True,
            last_started_at='2026-04-03T00:05:00Z',
            last_destroyed_at=None,
            last_destroy_reason=None,
        )
    )
    ProjectNamespaceEventStore(context.paths).append(
        ProjectNamespaceEvent(
            event_kind='namespace_created',
            project_id=context.project.project_id,
            occurred_at='2026-04-03T00:05:00Z',
            namespace_epoch=4,
            tmux_socket_path=str(context.paths.ccbd_tmux_socket_path),
            tmux_session_name=context.paths.ccbd_tmux_session_name,
            details={'recreated': False},
        )
    )

    payload = doctor_summary(context)

    assert payload['ccbd']['namespace_epoch'] == 4
    assert payload['ccbd']['namespace_tmux_socket_path'] == str(context.paths.ccbd_tmux_socket_path)
    assert payload['ccbd']['namespace_tmux_session_name'] == context.paths.ccbd_tmux_session_name
    assert payload['ccbd']['namespace_last_event_kind'] == 'namespace_created'
    assert payload['ccbd']['namespace_last_event_at'] == '2026-04-03T00:05:00Z'


def test_doctor_summary_includes_startup_and_shutdown_report_fields(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-doctor-reports'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    context = CliContextBuilder().build(ParsedDoctorCommand(project=None), cwd=project_root, bootstrap_if_missing=False)

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
            daemon_generation=2,
            daemon_started=True,
            config_signature='sig-1',
            inspection={},
            restore_summary={},
            actions_taken=('launch_runtime:demo',),
            cleanup_summaries=(),
            agent_results=(),
            failure_reason=None,
        )
    )
    CcbdShutdownReportStore(context.paths).save(
        CcbdShutdownReport(
            project_id=context.project.project_id,
            generated_at='2026-04-03T00:10:00Z',
            trigger='kill',
            status='ok',
            forced=False,
            stopped_agents=('demo',),
            daemon_generation=2,
            reason='kill',
            inspection_after={},
            actions_taken=('request_shutdown_intent',),
            cleanup_summaries=(),
            runtime_snapshots=(),
            failure_reason=None,
        )
    )

    payload = doctor_summary(context)

    assert payload['ccbd']['startup_last_trigger'] == 'start_command'
    assert payload['ccbd']['startup_last_status'] == 'ok'
    assert payload['ccbd']['startup_last_daemon_started'] is True
    assert payload['ccbd']['shutdown_last_trigger'] == 'kill'
    assert payload['ccbd']['shutdown_last_status'] == 'ok'
    assert payload['ccbd']['shutdown_last_reason'] == 'kill'
