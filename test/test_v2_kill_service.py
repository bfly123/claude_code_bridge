from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from agents.models import AgentRuntime, AgentState
from agents.store import AgentRuntimeStore
from ccbd.lifecycle_report_store import CcbdShutdownReportStore
from ccbd.models import LeaseHealth
from ccbd.services.start_policy import CcbdStartPolicy, CcbdStartPolicyStore
from cli.context import CliContextBuilder
from cli.services.daemon import CcbdServiceError
from cli.models import ParsedKillCommand
from cli.services.daemon import KillSummary, shutdown_daemon
from cli.services.kill import kill_project
from cli.services.tmux_project_cleanup import ProjectTmuxCleanupSummary
from project.resolver import bootstrap_project


def _namespace_controller(*, destroyed: bool):
    return lambda paths, project_id: SimpleNamespace(
        destroy=lambda **kwargs: SimpleNamespace(
            destroyed=destroyed,
            namespace_epoch=1,
            tmux_socket_path=str(getattr(paths, 'ccbd_tmux_socket_path', '')),
            tmux_session_name='ccb-test',
            reason=str(kwargs.get('reason') or 'kill'),
        )
    )


def test_kill_project_returns_tmux_cleanup_summary(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-kill-cleanup'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedKillCommand(project=None, force=True)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    monkeypatch.setattr(
        'cli.services.kill.shutdown_daemon',
        lambda context, force: KillSummary(
            project_id=context.project.project_id,
            state='unmounted',
            socket_path=str(context.paths.ccbd_socket_path),
            forced=force,
        ),
    )
    monkeypatch.setattr('cli.services.kill.set_tmux_ui_active', lambda active: None)
    monkeypatch.setattr('cli.services.kill.ProjectNamespaceController', _namespace_controller(destroyed=False))
    monkeypatch.setattr(
        'cli.services.kill.cleanup_project_tmux_orphans_by_socket',
        lambda **kwargs: (
            ProjectTmuxCleanupSummary(
                socket_name=None,
                owned_panes=('%1',),
                active_panes=(),
                orphaned_panes=('%1',),
                killed_panes=('%1',),
            ),
        ),
    )
    monkeypatch.setattr(
        'cli.services.kill.TmuxCleanupHistoryStore',
        lambda paths: type('Store', (), {'append': staticmethod(lambda event: None)})(),
    )

    summary = kill_project(context, command)

    assert len(summary.cleanup_summaries) == 1
    assert summary.cleanup_summaries[0].killed_panes == ('%1',)


def test_kill_project_writes_shutdown_report_after_remote_stop_all(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-kill-report-remote'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedKillCommand(project=None, force=False)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)
    AgentRuntimeStore(context.paths).save(
        AgentRuntime(
            agent_name='demo',
            state=AgentState.STOPPED,
            pid=None,
            started_at='2026-04-03T00:00:00Z',
            last_seen_at='2026-04-03T00:00:01Z',
            runtime_ref=None,
            session_ref=None,
            workspace_path=str(context.paths.workspace_path('demo')),
            project_id=context.project.project_id,
            backend_type='tmux',
            queue_depth=0,
            socket_path=None,
            health='stopped',
            desired_state='stopped',
            reconcile_state='stopped',
        )
    )

    class _FakeClient:
        def stop_all(self, *, force: bool):
            assert force is False
            return {
                'project_id': context.project.project_id,
                'state': 'unmounted',
                'socket_path': str(context.paths.ccbd_socket_path),
                'forced': False,
                'stopped_agents': ['demo'],
                'cleanup_summaries': [],
            }

    monkeypatch.setattr(
        'cli.services.kill.connect_mounted_daemon',
        lambda context, allow_restart_stale: SimpleNamespace(client=_FakeClient()),
    )
    monkeypatch.setattr(
        'cli.services.kill.inspect_daemon',
        lambda context: (
            None,
            None,
            SimpleNamespace(
                socket_connectable=False,
                health=LeaseHealth.UNMOUNTED,
                lease=SimpleNamespace(mount_state=SimpleNamespace(value='unmounted')),
            ),
        ),
    )
    monkeypatch.setattr('cli.services.kill.set_tmux_ui_active', lambda active: None)
    monkeypatch.setattr('cli.services.kill.ProjectNamespaceController', _namespace_controller(destroyed=True))
    monkeypatch.setattr('cli.services.kill.cleanup_project_tmux_orphans_by_socket', lambda **kwargs: ())

    summary = kill_project(context, command)
    report = CcbdShutdownReportStore(context.paths).load()

    assert summary.state == 'unmounted'
    assert report is not None
    assert report.trigger == 'kill'
    assert report.reason == 'kill'
    assert report.status == 'ok'
    assert report.stopped_agents == ('demo',)


def test_kill_project_clears_start_policy(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-kill-policy'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedKillCommand(project=None, force=False)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)
    CcbdStartPolicyStore(context.paths).save(
        CcbdStartPolicy(
            project_id=context.project.project_id,
            auto_permission=True,
            recovery_restore=True,
            last_started_at='2026-04-03T00:00:00Z',
            source='start_command',
        )
    )

    monkeypatch.setattr(
        'cli.services.kill.connect_mounted_daemon',
        lambda context, allow_restart_stale: SimpleNamespace(client=None),
    )
    monkeypatch.setattr(
        'cli.services.kill.shutdown_daemon',
        lambda context, force: KillSummary(
            project_id=context.project.project_id,
            state='unmounted',
            socket_path=str(context.paths.ccbd_socket_path),
            forced=force,
        ),
    )
    monkeypatch.setattr('cli.services.kill.set_tmux_ui_active', lambda active: None)
    monkeypatch.setattr('cli.services.kill.ProjectNamespaceController', _namespace_controller(destroyed=True))
    monkeypatch.setattr('cli.services.kill.cleanup_project_tmux_orphans_by_socket', lambda **kwargs: ())

    kill_project(context, command)

    assert CcbdStartPolicyStore(context.paths).load() is None


def test_kill_project_remote_stop_all_still_runs_local_cleanup(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-kill-remote-hard-cleanup'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedKillCommand(project=None, force=False)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)
    seen: dict[str, object] = {}

    class _FakeClient:
        def stop_all(self, *, force: bool):
            assert force is False
            seen['remote_stop_all'] = True
            return {
                'project_id': context.project.project_id,
                'state': 'unmounted',
                'socket_path': str(context.paths.ccbd_socket_path),
                'forced': False,
                'cleanup_summaries': [],
            }

    monkeypatch.setattr(
        'cli.services.kill.connect_mounted_daemon',
        lambda context, allow_restart_stale: SimpleNamespace(client=_FakeClient()),
    )

    monkeypatch.setattr(
        'cli.services.kill.inspect_daemon',
        lambda context: (
            None,
            None,
            SimpleNamespace(
                socket_connectable=False,
                health=LeaseHealth.UNMOUNTED,
                lease=SimpleNamespace(mount_state=SimpleNamespace(value='unmounted')),
            ),
        ),
    )
    monkeypatch.delenv('TMUX', raising=False)
    monkeypatch.delenv('CCB_TMUX_SOCKET', raising=False)
    monkeypatch.setattr('cli.services.kill.set_tmux_ui_active', lambda active: None)
    monkeypatch.setattr('cli.services.kill.ProjectNamespaceController', _namespace_controller(destroyed=True))

    def _cleanup(**kwargs):
        seen['cleanup'] = kwargs['active_panes_by_socket']
        return ()

    monkeypatch.setattr('cli.services.kill.cleanup_project_tmux_orphans_by_socket', _cleanup)

    summary = kill_project(context, command)

    assert seen['remote_stop_all'] is True
    assert 'shutdown_daemon' not in seen
    assert seen['cleanup'] == {None: ()}
    assert summary.state == 'unmounted'


def test_kill_project_uses_current_tmux_socket_when_binding_missing(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-kill-current-socket'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedKillCommand(project=None, force=True)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)
    seen: dict[str, object] = {}

    monkeypatch.setenv('TMUX', '/tmp/tmux-1000/ccb,123,0')
    monkeypatch.setattr(
        'cli.services.kill.shutdown_daemon',
        lambda context, force: KillSummary(
            project_id=context.project.project_id,
            state='unmounted',
            socket_path=str(context.paths.ccbd_socket_path),
            forced=force,
        ),
    )
    monkeypatch.setattr('cli.services.kill.set_tmux_ui_active', lambda active: None)
    monkeypatch.setattr('cli.services.kill.ProjectNamespaceController', _namespace_controller(destroyed=False))

    def _cleanup(**kwargs):
        seen['active_panes_by_socket'] = kwargs['active_panes_by_socket']
        return ()

    monkeypatch.setattr('cli.services.kill.cleanup_project_tmux_orphans_by_socket', _cleanup)
    monkeypatch.setattr(
        'cli.services.kill.TmuxCleanupHistoryStore',
        lambda paths: type('Store', (), {'append': staticmethod(lambda event: None)})(),
    )

    kill_project(context, command)

    assert seen['active_panes_by_socket'] == {'ccb': ()}


def test_kill_project_terminates_runtime_pid_files(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-kill-pids'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedKillCommand(project=None, force=False)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    runtime_dir = context.paths.agent_provider_runtime_dir('demo', 'codex')
    runtime_dir.mkdir(parents=True, exist_ok=True)
    bridge_pid = runtime_dir / 'bridge.pid'
    codex_pid = runtime_dir / 'codex.pid'
    bridge_pid.write_text('111\n', encoding='utf-8')
    codex_pid.write_text('222\n', encoding='utf-8')
    AgentRuntimeStore(context.paths).save(
        AgentRuntime(
            agent_name='demo',
            state=AgentState.IDLE,
            pid=333,
            started_at='2026-04-01T00:00:00Z',
            last_seen_at='2026-04-01T00:00:00Z',
            runtime_ref='tmux:%1',
            session_ref=str(project_root / '.ccb' / '.codex-demo-session'),
            workspace_path=str(context.paths.workspace_path('demo')),
            project_id=context.project.project_id,
            backend_type='pane-backed',
            queue_depth=2,
            socket_path=str(context.paths.ccbd_socket_path),
            health='healthy',
        )
    )

    terminated: list[int] = []
    monkeypatch.setattr(
        'cli.services.kill.shutdown_daemon',
        lambda context, force: KillSummary(
            project_id=context.project.project_id,
            state='unmounted',
            socket_path=str(context.paths.ccbd_socket_path),
            forced=force,
        ),
    )
    monkeypatch.setattr('cli.services.kill.set_tmux_ui_active', lambda active: None)
    monkeypatch.setattr('cli.services.kill.ProjectNamespaceController', _namespace_controller(destroyed=False))
    monkeypatch.setattr('cli.services.kill.cleanup_project_tmux_orphans_by_socket', lambda **kwargs: ())
    monkeypatch.setattr(
        'cli.services.kill.TmuxCleanupHistoryStore',
        lambda paths: type('Store', (), {'append': staticmethod(lambda event: None)})(),
    )
    monkeypatch.setattr('cli.services.kill._pid_matches_project', lambda pid, project_root, hint_paths: True)
    monkeypatch.setattr('cli.services.kill.is_pid_alive', lambda pid: pid in {111, 222, 333})
    monkeypatch.setattr(
        'cli.services.kill.terminate_pid_tree',
        lambda pid, timeout_s, is_pid_alive_fn: terminated.append(pid) or True,
    )

    kill_project(context, command)

    assert terminated == [111, 222, 333]
    assert bridge_pid.exists() is False
    assert codex_pid.exists() is False
    runtime = AgentRuntimeStore(context.paths).load('demo')
    assert runtime is not None
    assert runtime.state is AgentState.STOPPED
    assert runtime.pid is None
    assert runtime.runtime_ref is None
    assert runtime.desired_state == 'stopped'
    assert runtime.reconcile_state == 'stopped'


def test_shutdown_daemon_terminates_lingering_ccbd_pid(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-kill-daemon-pid'
    project_root.mkdir(parents=True, exist_ok=True)
    bootstrap_project(project_root)
    command = ParsedKillCommand(project=None, force=False)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    lease = SimpleNamespace(
        mount_state=SimpleNamespace(value='unmounted'),
        ccbd_pid=321,
    )
    mark_calls: list[str] = []
    manager = SimpleNamespace(
        mark_unmounted=lambda: mark_calls.append('unmounted') or lease,
        load_state=lambda: lease,
    )
    inspection = SimpleNamespace(
        socket_connectable=True,
        pid_alive=True,
        lease=lease,
    )
    client_calls: list[str] = []
    terminated: list[int] = []

    class FakeClient:
        def __init__(self, _path):
            pass

        def shutdown(self):
            client_calls.append('shutdown')

    monkeypatch.setattr('cli.services.daemon.inspect_daemon', lambda context: (manager, None, inspection))
    monkeypatch.setattr('cli.services.daemon.CcbdClient', FakeClient)
    monkeypatch.setattr('cli.services.daemon._wait_for_pid_exit', lambda pid, timeout_s: False)
    monkeypatch.setattr('cli.services.daemon.is_pid_alive', lambda pid: False)
    monkeypatch.setattr(
        'cli.services.daemon.terminate_pid_tree',
        lambda pid, timeout_s, is_pid_alive_fn: terminated.append(pid) or True,
    )

    summary = shutdown_daemon(context, force=False)

    assert client_calls == ['shutdown']
    assert terminated == [321]
    assert mark_calls == ['unmounted']
    assert summary.state == 'unmounted'


def test_kill_project_force_ignores_invalid_runtime_file_for_unknown_agent(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-kill-invalid-extra-runtime'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedKillCommand(project=None, force=True)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    invalid_runtime = context.paths.agent_runtime_path('legacy')
    invalid_runtime.parent.mkdir(parents=True, exist_ok=True)
    invalid_runtime.write_text('{"agent_name":"legacy"}\n', encoding='utf-8')

    monkeypatch.setattr('cli.services.kill.connect_mounted_daemon', lambda context, allow_restart_stale: (_ for _ in ()).throw(CcbdServiceError('down')))
    monkeypatch.setattr('cli.services.kill.ProjectNamespaceController', _namespace_controller(destroyed=False))
    monkeypatch.setattr(
        'cli.services.kill.shutdown_daemon',
        lambda context, force: KillSummary(
            project_id=context.project.project_id,
            state='unmounted',
            socket_path=str(context.paths.ccbd_socket_path),
            forced=force,
        ),
    )
    monkeypatch.setattr('cli.services.kill.set_tmux_ui_active', lambda active: None)
    monkeypatch.setattr('cli.services.kill.cleanup_project_tmux_orphans_by_socket', lambda **kwargs: ())
    monkeypatch.setattr(
        'cli.services.kill.TmuxCleanupHistoryStore',
        lambda paths: type('Store', (), {'append': staticmethod(lambda event: None)})(),
    )

    summary = kill_project(context, command)

    assert summary.state == 'unmounted'


def test_kill_project_fallback_writes_shutdown_report(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-kill-report-fallback'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedKillCommand(project=None, force=True)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)
    AgentRuntimeStore(context.paths).save(
        AgentRuntime(
            agent_name='demo',
            state=AgentState.STOPPED,
            pid=None,
            started_at='2026-04-03T00:00:00Z',
            last_seen_at='2026-04-03T00:00:01Z',
            runtime_ref=None,
            session_ref=None,
            workspace_path=str(context.paths.workspace_path('demo')),
            project_id=context.project.project_id,
            backend_type='tmux',
            queue_depth=0,
            socket_path=None,
            health='stopped',
            desired_state='stopped',
            reconcile_state='stopped',
        )
    )

    monkeypatch.setattr('cli.services.kill.connect_mounted_daemon', lambda context, allow_restart_stale: (_ for _ in ()).throw(CcbdServiceError('down')))
    monkeypatch.setattr('cli.services.kill.ProjectNamespaceController', _namespace_controller(destroyed=False))
    monkeypatch.setattr(
        'cli.services.kill.shutdown_daemon',
        lambda context, force: KillSummary(
            project_id=context.project.project_id,
            state='unmounted',
            socket_path=str(context.paths.ccbd_socket_path),
            forced=force,
        ),
    )
    monkeypatch.setattr('cli.services.kill.set_tmux_ui_active', lambda active: None)
    monkeypatch.setattr('cli.services.kill.cleanup_project_tmux_orphans_by_socket', lambda **kwargs: ())
    monkeypatch.setattr(
        'cli.services.kill.TmuxCleanupHistoryStore',
        lambda paths: type('Store', (), {'append': staticmethod(lambda event: None)})(),
    )

    kill_project(context, command)
    report = CcbdShutdownReportStore(context.paths).load()

    assert report is not None
    assert report.trigger == 'kill_fallback'
    assert report.reason == 'kill'
    assert report.status == 'ok'


def test_kill_project_fallback_still_cleans_external_tmux_after_namespace_destroy(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-kill-namespace-first'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedKillCommand(project=None, force=True)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    monkeypatch.setattr('cli.services.kill.connect_mounted_daemon', lambda context, allow_restart_stale: (_ for _ in ()).throw(CcbdServiceError('down')))
    monkeypatch.setattr('cli.services.kill.ProjectNamespaceController', _namespace_controller(destroyed=True))
    monkeypatch.setattr(
        'cli.services.kill.shutdown_daemon',
        lambda context, force: KillSummary(
            project_id=context.project.project_id,
            state='unmounted',
            socket_path=str(context.paths.ccbd_socket_path),
            forced=force,
        ),
    )
    monkeypatch.setattr('cli.services.kill.set_tmux_ui_active', lambda active: None)
    monkeypatch.setattr(
        'cli.services.kill.cleanup_project_tmux_orphans_by_socket',
        lambda **kwargs: (
            ProjectTmuxCleanupSummary(
                socket_name=None,
                owned_panes=('%7',),
                active_panes=(),
                orphaned_panes=('%7',),
                killed_panes=('%7',),
            ),
        ),
    )

    summary = kill_project(context, command)

    assert len(summary.cleanup_summaries) == 1
    assert summary.cleanup_summaries[0].killed_panes == ('%7',)
