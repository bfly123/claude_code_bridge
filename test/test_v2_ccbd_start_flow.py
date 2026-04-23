from __future__ import annotations

from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

from ccbd.app import CcbdApp
from ccbd.lifecycle_report_store import CcbdStartupReportStore
from ccbd.models import CcbdStartupReport
from ccbd.start_flow import StartFlowSummary
from ccbd.start_flow_runtime.service_tmux import project_socket_active_panes
from ccbd.socket_client import CcbdClient
from cli.services.provider_binding import AgentBinding
from cli.services.runtime_launch import RuntimeLaunchResult
from cli.services.tmux_project_cleanup import ProjectTmuxCleanupSummary
from project.resolver import bootstrap_project
import pytest


def _client(app: CcbdApp, *, timeout_s: float | None = None) -> CcbdClient:
    return CcbdClient(app.paths.ccbd_ipc_ref, timeout_s=timeout_s, ipc_kind=app.paths.ccbd_ipc_kind)


def _ready_ping_timeout_s(app: CcbdApp) -> float:
    return 1.0 if app.paths.ccbd_ipc_kind == 'named_pipe' else 0.2


def _wait_for_app_ready(app: CcbdApp, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    startup_store = CcbdStartupReportStore(app.paths)
    last_error: Exception | None = None
    while time.time() < deadline:
        if app.paths.ccbd_ipc_kind != 'named_pipe' and not app.paths.ccbd_socket_path.exists():
            time.sleep(0.02)
            continue
        if startup_store.load() is None:
            time.sleep(0.02)
            continue
        try:
            if _client(app, timeout_s=_ready_ping_timeout_s(app)).ping('ccbd').get('mount_state') == 'mounted':
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.02)
    detail = f'; last_error={last_error}' if last_error is not None else ''
    raise AssertionError(f'timed out waiting for ccbd readiness: {app.paths.ccbd_ipc_ref}{detail}')


def test_ccbd_start_flow_client_helper_uses_ipc_ref_and_kind(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-ccbd-start-helper'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)

    client = _client(app, timeout_s=1.5)

    assert client._socket_path == app.paths.ccbd_ipc_ref
    assert client._ipc_kind == app.paths.ccbd_ipc_kind
    assert client._timeout_s == 1.5


def test_ccbd_start_flow_wait_for_app_ready_uses_named_pipe_probe_timeout(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-start-ready-helper-named-pipe'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    monkeypatch.setenv('CCB_EXPERIMENTAL_WINDOWS_NATIVE', '1')
    monkeypatch.setenv('CCB_IPC_KIND', 'named_pipe')
    app = CcbdApp(project_root)
    app.startup_report_store.save(
        CcbdStartupReport(
            project_id=app.project_id,
            generated_at='2026-04-21T00:00:00Z',
            trigger='daemon_boot',
            status='ok',
            requested_agents=(),
            desired_agents=('demo',),
            restore_requested=False,
            auto_permission=False,
            daemon_generation=1,
            daemon_started=True,
            config_signature='sig',
            inspection={},
            restore_summary={},
            actions_taken=('mount_backend', 'listen_socket', 'restore_running_jobs'),
            cleanup_summaries=(),
            agent_results=(),
            failure_reason=None,
        )
    )
    seen: list[tuple[float | None, str]] = []

    def _fake_client(current_app: CcbdApp, *, timeout_s: float | None = None):
        assert current_app is app
        return SimpleNamespace(
            ping=lambda target: seen.append((timeout_s, target)) or {'mount_state': 'mounted'}
        )

    monkeypatch.setattr(sys.modules[__name__], '_client', _fake_client)

    _wait_for_app_ready(app, timeout=0.2)

    assert seen == [(1.0, 'ccbd')]


class _FakeNamespaceTmuxBackend:
    def __init__(self, *, socket_path: str | None = None):
        self.socket_path = socket_path

    def _tmux_run(self, args, *, capture=False, check=False, input_bytes=None, timeout=None):
        del capture, check, input_bytes, timeout
        if args[:3] == ['list-panes', '-t', 'ccb-repo-ccbd-start']:
            return SimpleNamespace(stdout='%0\n')
        if args[:2] == ['list-panes', '-t']:
            return SimpleNamespace(stdout='%0\n')
        raise AssertionError(f'unexpected tmux args: {args}')


def test_project_socket_active_panes_preserves_namespace_root_without_cmd() -> None:
    active_panes, cmd_pane_id = project_socket_active_panes(
        tmux_layout=SimpleNamespace(cmd_pane_id=None, agent_panes={}),
        tmux_socket_path='/tmp/ccb.sock',
        config=SimpleNamespace(cmd_enabled=False),
        root_pane_id='%0',
    )

    assert active_panes == ['%0']
    assert cmd_pane_id is None


def test_ccbd_start_flow_writes_runtime_authority_via_rpc(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-start'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('cmd; demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)
    monkeypatch.setattr(
        app.project_namespace,
        'ensure',
        lambda: SimpleNamespace(
            tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
            tmux_session_name=app.paths.ccbd_tmux_session_name,
            namespace_epoch=1,
        ),
    )
    monkeypatch.setattr('ccbd.start_flow.TmuxBackend', _FakeNamespaceTmuxBackend)

    monkeypatch.setattr('ccbd.start_flow.set_tmux_ui_active', lambda active: None)
    monkeypatch.setattr(
        'ccbd.start_flow.prepare_tmux_start_layout',
        lambda context, config, targets, **kwargs: SimpleNamespace(cmd_pane_id=None, agent_panes={}),
    )
    monkeypatch.setattr('ccbd.start_flow.cleanup_project_tmux_orphans_by_socket', lambda **kwargs: ())
    monkeypatch.setattr(
        'ccbd.start_flow.TmuxCleanupHistoryStore',
        lambda paths: SimpleNamespace(append=lambda event: None),
    )
    monkeypatch.setattr('ccbd.start_flow.resolve_agent_binding', lambda **kwargs: None)
    monkeypatch.setattr(
        'ccbd.start_flow.ensure_agent_runtime',
        lambda *args, **kwargs: RuntimeLaunchResult(
            launched=True,
            binding=AgentBinding(
                runtime_ref='tmux:%901',
                session_ref='session-901',
                provider='codex',
                runtime_root=str(app.paths.agent_provider_runtime_dir('demo', 'codex')),
                runtime_pid=901,
                session_file=str(project_root / '.ccb' / 'demo.session.json'),
                session_id='session-901',
                tmux_socket_name='sock-a',
                tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
                terminal='tmux',
                pane_id='%901',
                active_pane_id='%901',
                pane_title_marker='CCB-demo',
                pane_state='alive',
            ),
        ),
    )

    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for_app_ready(app)

    client = _client(app)
    payload = client.start(agent_names=('demo',), restore=False, auto_permission=False)
    runtime = app.registry.get('demo')

    assert payload['started'] == ['demo']
    assert payload['project_id'] == app.project_id
    assert runtime is not None
    assert runtime.runtime_ref == 'tmux:%901'
    assert runtime.session_ref == 'session-901'
    assert runtime.runtime_root == str(app.paths.agent_provider_runtime_dir('demo', 'codex'))
    assert runtime.runtime_pid == 901
    assert runtime.tmux_socket_name == 'sock-a'
    assert runtime.tmux_socket_path == str(app.paths.ccbd_tmux_socket_path)
    assert runtime.binding_source.value == 'provider-session'
    assert runtime.managed_by == 'ccbd'
    assert runtime.lifecycle_state == 'idle'

    client.shutdown()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_runtime_supervisor_start_can_skip_tmux_cleanup_and_layout_for_background_mount(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-start-no-cleanup'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('cmd; demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)
    monkeypatch.setattr(
        app.project_namespace,
        'ensure',
        lambda: SimpleNamespace(
            tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
            tmux_session_name=app.paths.ccbd_tmux_session_name,
            namespace_epoch=2,
        ),
    )
    monkeypatch.setattr('ccbd.start_flow.TmuxBackend', _FakeNamespaceTmuxBackend)

    monkeypatch.setattr('ccbd.start_flow.set_tmux_ui_active', lambda active: (_ for _ in ()).throw(AssertionError('tmux ui should be skipped')))
    monkeypatch.setattr(
        'ccbd.start_flow.prepare_tmux_start_layout',
        lambda context, config, targets, **kwargs: (_ for _ in ()).throw(AssertionError('interactive layout should be skipped')),
    )
    monkeypatch.setattr('ccbd.start_flow.cleanup_project_tmux_orphans_by_socket', lambda **kwargs: (_ for _ in ()).throw(AssertionError('cleanup should be skipped')))
    monkeypatch.setattr(
        'ccbd.start_flow.TmuxCleanupHistoryStore',
        lambda paths: SimpleNamespace(append=lambda event: (_ for _ in ()).throw(AssertionError('cleanup history should be skipped'))),
    )
    monkeypatch.setattr('ccbd.start_flow.resolve_agent_binding', lambda **kwargs: None)
    monkeypatch.setattr(
        'ccbd.start_flow.ensure_agent_runtime',
        lambda *args, **kwargs: RuntimeLaunchResult(
            launched=True,
            binding=AgentBinding(
                runtime_ref='tmux:%777',
                session_ref='session-777',
                provider='codex',
                runtime_root=str(app.paths.agent_provider_runtime_dir('demo', 'codex')),
                runtime_pid=777,
                session_file=str(project_root / '.ccb' / 'demo.session.json'),
                session_id='session-777',
                tmux_socket_name='sock-a',
                tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
                terminal='tmux',
                pane_id='%777',
                active_pane_id='%777',
                pane_title_marker='CCB-demo',
                pane_state='alive',
            ),
        ),
    )

    summary = app.runtime_supervisor.start(
        agent_names=('demo',),
        restore=False,
        auto_permission=False,
        cleanup_tmux_orphans=False,
        interactive_tmux_layout=False,
    )

    assert summary.started == ('demo',)
    assert summary.cleanup_summaries == ()
    runtime = app.registry.get('demo')
    assert runtime is not None
    assert runtime.runtime_ref == 'tmux:%777'
    assert runtime.tmux_socket_path == str(app.paths.ccbd_tmux_socket_path)


def test_runtime_supervisor_start_persists_startup_report(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-start-report'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('cmd; demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)
    app.lease = app.mount_manager.mark_mounted(
        project_id=app.project_id,
        pid=4321,
        socket_path=app.paths.ccbd_socket_path,
        generation=3,
        config_signature=str(app.config_identity['config_signature']),
    )
    monkeypatch.setattr(
        app.project_namespace,
        'ensure',
        lambda: SimpleNamespace(
            tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
            tmux_session_name=app.paths.ccbd_tmux_session_name,
            namespace_epoch=7,
        ),
    )
    monkeypatch.setattr('ccbd.start_flow.TmuxBackend', _FakeNamespaceTmuxBackend)

    monkeypatch.setattr('ccbd.start_flow.set_tmux_ui_active', lambda active: None)
    monkeypatch.setattr(
        'ccbd.start_flow.prepare_tmux_start_layout',
        lambda context, config, targets, **kwargs: SimpleNamespace(cmd_pane_id=None, agent_panes={}),
    )
    monkeypatch.setattr('ccbd.start_flow.cleanup_project_tmux_orphans_by_socket', lambda **kwargs: ())
    monkeypatch.setattr(
        'ccbd.start_flow.TmuxCleanupHistoryStore',
        lambda paths: SimpleNamespace(append=lambda event: None),
    )
    monkeypatch.setattr('ccbd.start_flow.resolve_agent_binding', lambda **kwargs: None)
    monkeypatch.setattr(
        'ccbd.start_flow.ensure_agent_runtime',
        lambda *args, **kwargs: RuntimeLaunchResult(
            launched=True,
            binding=AgentBinding(
                runtime_ref='tmux:%880',
                session_ref='session-880',
                provider='codex',
                runtime_root=str(app.paths.agent_provider_runtime_dir('demo', 'codex')),
                runtime_pid=880,
                session_file=str(project_root / '.ccb' / 'demo.session.json'),
                session_id='session-880',
                tmux_socket_name='sock-a',
                tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
                terminal='tmux',
                pane_id='%880',
                active_pane_id='%880',
                pane_title_marker='CCB-demo',
                pane_state='alive',
            ),
        ),
    )

    summary = app.runtime_supervisor.start(
        agent_names=('demo',),
        restore=False,
        auto_permission=False,
        cleanup_tmux_orphans=False,
        interactive_tmux_layout=False,
    )
    report = CcbdStartupReportStore(app.paths).load()

    assert summary.started == ('demo',)
    assert report is not None
    assert report.trigger == 'start_command'
    assert report.status == 'ok'
    assert report.daemon_generation == 3
    assert report.requested_agents == ('demo',)
    assert report.daemon_started is None
    assert report.actions_taken == (
        f'ensure_namespace:epoch=7,session={app.paths.ccbd_tmux_session_name}',
        'launch_runtime:demo',
    )
    assert len(report.agent_results) == 1
    assert report.agent_results[0].agent_name == 'demo'
    assert report.agent_results[0].action == 'launched'
    assert report.agent_results[0].session_file == str(project_root / '.ccb' / 'demo.session.json')
    assert report.agent_results[0].session_id == 'session-880'
    assert report.agent_results[0].job_id is None
    assert report.agent_results[0].job_owner_pid is None


def test_runtime_supervisor_start_passes_visible_layout_signature_to_namespace(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-layout-signature-pass'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('cmd, agent1:codex; agent2:codex, agent3:claude\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)
    seen: dict[str, object] = {}

    class FakeProjectNamespace:
        def ensure(self, *, layout_signature=None, force_recreate=False, recreate_reason=None):
            seen['layout_signature'] = layout_signature
            seen['force_recreate'] = force_recreate
            seen['recreate_reason'] = recreate_reason
            return SimpleNamespace(
                tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
                tmux_session_name=app.paths.ccbd_tmux_session_name,
                namespace_epoch=9,
                created_this_call=False,
            )

    monkeypatch.setattr(app.runtime_supervisor, '_project_namespace', FakeProjectNamespace())
    monkeypatch.setattr(
        'ccbd.supervisor.run_start_flow',
        lambda **kwargs: StartFlowSummary(
            project_root=str(project_root),
            project_id=app.project_id,
            started=('agent1', 'agent2', 'agent3'),
            socket_path=str(app.paths.ccbd_socket_path),
        ),
    )

    app.runtime_supervisor.start(
        agent_names=('agent1', 'agent2', 'agent3'),
        restore=False,
        auto_permission=False,
        interactive_tmux_layout=True,
    )

    assert seen == {
        'layout_signature': 'cmd, agent1:codex; agent2:codex, agent3:claude',
        'force_recreate': False,
        'recreate_reason': None,
    }


def test_runtime_supervisor_background_mount_does_not_redefine_namespace_layout_signature(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-layout-signature-background'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('cmd, agent1:codex; agent2:codex, agent3:claude\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)
    seen: dict[str, object] = {}

    class FakeProjectNamespace:
        def ensure(self, *, layout_signature=None, force_recreate=False, recreate_reason=None):
            seen['layout_signature'] = layout_signature
            seen['force_recreate'] = force_recreate
            seen['recreate_reason'] = recreate_reason
            return SimpleNamespace(
                tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
                tmux_session_name=app.paths.ccbd_tmux_session_name,
                namespace_epoch=10,
                created_this_call=False,
            )

    monkeypatch.setattr(app.runtime_supervisor, '_project_namespace', FakeProjectNamespace())
    monkeypatch.setattr(
        'ccbd.supervisor.run_start_flow',
        lambda **kwargs: StartFlowSummary(
            project_root=str(project_root),
            project_id=app.project_id,
            started=('agent2',),
            socket_path=str(app.paths.ccbd_socket_path),
        ),
    )

    app.runtime_supervisor.start(
        agent_names=('agent2',),
        restore=True,
        auto_permission=True,
        interactive_tmux_layout=False,
        cleanup_tmux_orphans=False,
    )

    assert seen == {
        'layout_signature': None,
        'force_recreate': False,
        'recreate_reason': None,
    }


def test_runtime_supervisor_start_uses_generic_namespace_aliases_for_start_flow(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-start-generic-alias'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('agent1:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)
    seen: dict[str, object] = {}

    class FakeProjectNamespace:
        def ensure(self, *, layout_signature=None, force_recreate=False, recreate_reason=None):
            seen['layout_signature'] = layout_signature
            seen['force_recreate'] = force_recreate
            seen['recreate_reason'] = recreate_reason
            return SimpleNamespace(
                backend_ref=r'\\.\pipe\psmux-start',
                session_name='ccb-psmux-start',
                workspace_name='workspace-psmux-start',
                workspace_window_id='@5',
                workspace_epoch=4,
                namespace_epoch=11,
                created_this_call=True,
                workspace_recreated_this_call=True,
            )

    def _run_start_flow(**kwargs):
        seen['start_flow'] = kwargs
        return StartFlowSummary(
            project_root=str(project_root),
            project_id=app.project_id,
            started=('agent1',),
            socket_path=str(app.paths.ccbd_socket_path),
        )

    monkeypatch.setattr(app.runtime_supervisor, '_project_namespace', FakeProjectNamespace())
    monkeypatch.setattr('ccbd.supervisor.run_start_flow', _run_start_flow)

    summary = app.runtime_supervisor.start(
        agent_names=('agent1',),
        restore=False,
        auto_permission=False,
        interactive_tmux_layout=False,
    )

    assert summary.started == ('agent1',)
    assert seen['layout_signature'] is None
    assert seen['start_flow']['tmux_socket_path'] == r'\\.\pipe\psmux-start'
    assert seen['start_flow']['tmux_session_name'] == 'ccb-psmux-start'
    assert seen['start_flow']['tmux_workspace_window_name'] == 'workspace-psmux-start'
    assert seen['start_flow']['workspace_window_id'] == '@5'
    assert seen['start_flow']['workspace_epoch'] == 4
    assert seen['start_flow']['namespace_epoch'] == 11
    assert seen['start_flow']['fresh_namespace'] is True
    assert seen['start_flow']['fresh_workspace'] is True


def test_runtime_supervisor_relabels_reused_project_namespace_pane_by_agent_name(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-relabel'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('cmd; demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)
    monkeypatch.setattr(
        app.project_namespace,
        'ensure',
        lambda: SimpleNamespace(
            tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
            tmux_session_name=app.paths.ccbd_tmux_session_name,
            namespace_epoch=3,
        ),
    )

    relabel_calls: list[dict[str, object]] = []

    class FakeTmuxBackend:
        def __init__(self, *, socket_path: str | None = None):
            self.socket_path = socket_path

        def _tmux_run(self, args, *, capture=False, check=False, input_bytes=None, timeout=None):
            del capture, check, input_bytes, timeout
            if args[:3] == ['display-message', '-p', '-t']:
                return SimpleNamespace(
                    returncode=0,
                    stdout=f"{args[3]}\t{app.paths.ccbd_tmux_session_name}\t0\tagent\tdemo\t{app.project_id}\tccbd\n",
                )
            raise AssertionError(f'unexpected tmux args: {args}')

        def set_pane_title(self, pane_id: str, title: str) -> None:
            del pane_id, title

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            del pane_id, name, value

    monkeypatch.setattr('ccbd.start_flow.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr(
        'ccbd.start_flow.apply_ccb_pane_identity',
        lambda backend, pane_id, **kwargs: relabel_calls.append(
            {
                'socket_path': getattr(backend, 'socket_path', None),
                'pane_id': pane_id,
                **kwargs,
            }
        ),
    )
    monkeypatch.setattr('ccbd.start_flow.resolve_agent_binding', lambda **kwargs: AgentBinding(
        runtime_ref='tmux:%77',
        session_ref='session-77',
        provider='codex',
        runtime_root=str(app.paths.agent_provider_runtime_dir('demo', 'codex')),
        runtime_pid=77,
        session_file=str(project_root / '.ccb' / '.codex-demo-session'),
        session_id='session-77',
        tmux_socket_name='sock-a',
        tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
        terminal='tmux',
        pane_id='%77',
        active_pane_id='%77',
        pane_title_marker='CCB-demo',
        pane_state='alive',
    ))
    monkeypatch.setattr(
        'ccbd.start_flow.ensure_agent_runtime',
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('should reuse existing binding')),
    )

    summary = app.runtime_supervisor.start(
        agent_names=('demo',),
        restore=False,
        auto_permission=False,
        cleanup_tmux_orphans=False,
        interactive_tmux_layout=False,
    )

    assert summary.started == ('demo',)
    assert relabel_calls == [
        {
            'socket_path': str(app.paths.ccbd_tmux_socket_path),
            'pane_id': '%77',
            'title': 'demo',
            'agent_label': 'demo',
            'project_id': app.project_id,
            'order_index': 0,
            'slot_key': 'demo',
            'namespace_epoch': 3,
            'managed_by': 'ccbd',
        }
    ]
    assert 'relabel_runtime_pane:demo:%77' in summary.actions_taken


def test_runtime_supervisor_relaunches_same_socket_binding_outside_namespace_session(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-foreign-session'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('cmd; demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)
    monkeypatch.setattr(
        app.project_namespace,
        'ensure',
        lambda: SimpleNamespace(
            tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
            tmux_session_name=app.paths.ccbd_tmux_session_name,
            namespace_epoch=5,
        ),
    )

    class FakeTmuxBackend:
        def __init__(self, *, socket_path: str | None = None):
            self.socket_path = socket_path

        def _tmux_run(self, args, *, capture=False, check=False, input_bytes=None, timeout=None):
            del capture, check, input_bytes, timeout
            if args[:3] == ['list-panes', '-t', app.paths.ccbd_tmux_session_name]:
                return SimpleNamespace(stdout='%0\n')
            if args[:3] == ['display-message', '-p', '-t']:
                return SimpleNamespace(
                    returncode=0,
                    stdout=f"{args[3]}\tdetached-demo\t0\tagent\tdemo\t{app.project_id}\tccbd\n",
                )
            raise AssertionError(f'unexpected tmux args: {args}')

    monkeypatch.setattr('ccbd.start_flow.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr('ccbd.start_flow.set_tmux_ui_active', lambda active: None)
    monkeypatch.setattr('ccbd.start_flow.cleanup_project_tmux_orphans_by_socket', lambda **kwargs: ())
    monkeypatch.setattr(
        'ccbd.start_flow.TmuxCleanupHistoryStore',
        lambda paths: SimpleNamespace(append=lambda event: None),
    )
    monkeypatch.setattr(
        'ccbd.start_flow.prepare_tmux_start_layout',
        lambda context, config, targets, **kwargs: SimpleNamespace(cmd_pane_id='%0', agent_panes={'demo': '%55'}),
    )
    monkeypatch.setattr('ccbd.start_flow.resolve_agent_binding', lambda **kwargs: AgentBinding(
        runtime_ref='tmux:%77',
        session_ref='session-77',
        provider='codex',
        runtime_root=str(app.paths.agent_provider_runtime_dir('demo', 'codex')),
        runtime_pid=77,
        session_file=str(project_root / '.ccb' / '.codex-demo-session'),
        session_id='session-77',
        tmux_socket_name='sock-a',
        tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
        terminal='tmux',
        pane_id='%77',
        active_pane_id='%77',
        pane_title_marker='CCB-demo',
        pane_state='alive',
    ))
    launch_hints: list[object | None] = []
    monkeypatch.setattr(
        'ccbd.start_flow.ensure_agent_runtime',
        lambda *args, **kwargs: launch_hints.append(args[4]) or RuntimeLaunchResult(
            launched=True,
            binding=AgentBinding(
                runtime_ref='tmux:%55',
                session_ref='session-55',
                provider='codex',
                runtime_root=str(app.paths.agent_provider_runtime_dir('demo', 'codex')),
                runtime_pid=55,
                session_file=str(project_root / '.ccb' / '.codex-demo-session'),
                session_id='session-55',
                tmux_socket_name='sock-a',
                tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
                terminal='tmux',
                pane_id='%55',
                active_pane_id='%55',
                pane_title_marker='CCB-demo',
                pane_state='alive',
            ),
        ),
    )

    summary = app.runtime_supervisor.start(
        agent_names=('demo',),
        restore=False,
        auto_permission=False,
        cleanup_tmux_orphans=False,
        interactive_tmux_layout=True,
    )

    assert summary.started == ('demo',)
    assert launch_hints == [None]
    assert 'prepare_tmux_layout:demo' in summary.actions_taken
    assert 'relaunch_runtime:demo' in summary.actions_taken
    assert 'reuse_binding:demo' not in summary.actions_taken


def test_runtime_supervisor_bootstraps_fresh_cmd_pane_after_layout(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-fresh-cmd'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('cmd; demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)
    monkeypatch.setattr(
        app.project_namespace,
        'ensure',
        lambda: SimpleNamespace(
            tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
            tmux_session_name=app.paths.ccbd_tmux_session_name,
            namespace_epoch=8,
            created_this_call=True,
        ),
    )

    respawn_calls: list[dict[str, object]] = []

    class FakeTmuxBackend:
        def __init__(self, *, socket_path: str | None = None):
            self.socket_path = socket_path

        def _tmux_run(self, args, *, capture=False, check=False, input_bytes=None, timeout=None):
            del capture, check, input_bytes, timeout
            if args[:3] == ['list-panes', '-t', app.paths.ccbd_tmux_session_name]:
                return SimpleNamespace(stdout='%0\n')
            if args[:3] == ['display-message', '-p', '-t']:
                return SimpleNamespace(
                    returncode=0,
                    stdout=f"{args[3]}\t{app.paths.ccbd_tmux_session_name}\t0\tagent\tdemo\t{app.project_id}\tccbd\n",
                )
            raise AssertionError(f'unexpected tmux args: {args}')

        def respawn_pane(self, pane_id: str, *, cmd: str, cwd: str | None = None, stderr_log_path=None, remain_on_exit: bool = True) -> None:
            del stderr_log_path
            respawn_calls.append(
                {
                    'pane_id': pane_id,
                    'cmd': cmd,
                    'cwd': cwd,
                    'remain_on_exit': remain_on_exit,
                    'socket_path': self.socket_path,
                }
            )

        def set_pane_title(self, pane_id: str, title: str) -> None:
            del pane_id, title

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            del pane_id, name, value

    monkeypatch.setattr('ccbd.start_flow.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr('ccbd.start_flow.set_tmux_ui_active', lambda active: None)
    monkeypatch.setattr(
        'ccbd.start_flow.prepare_tmux_start_layout',
        lambda context, config, targets, **kwargs: SimpleNamespace(cmd_pane_id='%0', agent_panes={'demo': '%55'}),
    )
    monkeypatch.setattr('ccbd.start_flow.cleanup_project_tmux_orphans_by_socket', lambda **kwargs: ())
    monkeypatch.setattr(
        'ccbd.start_flow.TmuxCleanupHistoryStore',
        lambda paths: SimpleNamespace(append=lambda event: None),
    )
    monkeypatch.setattr('ccbd.start_flow.resolve_agent_binding', lambda **kwargs: None)
    monkeypatch.setattr(
        'ccbd.start_flow.ensure_agent_runtime',
        lambda *args, **kwargs: RuntimeLaunchResult(
            launched=True,
            binding=AgentBinding(
                runtime_ref='tmux:%55',
                session_ref='session-55',
                provider='codex',
                runtime_root=str(app.paths.agent_provider_runtime_dir('demo', 'codex')),
                runtime_pid=55,
                session_file=str(project_root / '.ccb' / '.codex-demo-session'),
                session_id='session-55',
                tmux_socket_name=None,
                tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
                terminal='tmux',
                pane_id='%55',
                active_pane_id='%55',
                pane_title_marker='CCB-demo',
                pane_state='alive',
            ),
        ),
    )

    summary = app.runtime_supervisor.start(
        agent_names=('demo',),
        restore=False,
        auto_permission=False,
        cleanup_tmux_orphans=False,
        interactive_tmux_layout=True,
    )

    assert summary.started == ('demo',)
    assert respawn_calls == [
        {
            'pane_id': '%0',
            'cmd': 'if [ -n "${SHELL:-}" ]; then exec "$SHELL" -l; fi; if command -v bash >/dev/null 2>&1; then exec bash -l; fi; exec sh',
            'cwd': str(project_root),
            'remain_on_exit': False,
            'socket_path': str(app.paths.ccbd_tmux_socket_path),
        }
    ]
    assert 'bootstrap_cmd_pane:%0' in summary.actions_taken


def test_runtime_supervisor_project_namespace_cleanup_uses_authoritative_active_panes(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-project-cleanup'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('cmd; demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)
    monkeypatch.setattr(
        app.project_namespace,
        'ensure',
        lambda: SimpleNamespace(
            tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
            tmux_session_name=app.paths.ccbd_tmux_session_name,
            namespace_epoch=9,
            created_this_call=False,
        ),
    )

    class FakeTmuxBackend:
        def __init__(self, *, socket_path: str | None = None):
            self.socket_path = socket_path

        def _tmux_run(self, args, *, capture=False, check=False, input_bytes=None, timeout=None):
            del capture, check, input_bytes, timeout
            if args[:3] == ['list-panes', '-t', app.paths.ccbd_tmux_session_name]:
                return SimpleNamespace(stdout='%0\n')
            if args[:3] == ['display-message', '-p', '-t']:
                return SimpleNamespace(
                    returncode=0,
                    stdout=f"{args[3]}\t{app.paths.ccbd_tmux_session_name}\t0\tagent\tdemo\t{app.project_id}\tccbd\n",
                )
            raise AssertionError(f'unexpected tmux args: {args}')

        def set_pane_title(self, pane_id: str, title: str) -> None:
            del pane_id, title

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            del pane_id, name, value

    cleanup_calls: list[dict[str, object]] = []
    history_events: list[object] = []

    monkeypatch.setattr('ccbd.start_flow.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr('ccbd.start_flow.set_tmux_ui_active', lambda active: None)
    monkeypatch.setattr(
        'ccbd.start_flow.prepare_tmux_start_layout',
        lambda context, config, targets, **kwargs: SimpleNamespace(cmd_pane_id='%0', agent_panes={'demo': '%55'}),
    )
    monkeypatch.setattr(
        'ccbd.start_flow.cleanup_project_tmux_orphans_by_socket',
        lambda **kwargs: cleanup_calls.append(kwargs) or (
            ProjectTmuxCleanupSummary(
                socket_name=str(app.paths.ccbd_tmux_socket_path),
                owned_panes=('%0', '%55', '%77'),
                active_panes=tuple(kwargs['active_panes_by_socket'][str(app.paths.ccbd_tmux_socket_path)]),
                orphaned_panes=('%77',),
                killed_panes=('%77',),
            ),
        ),
    )
    monkeypatch.setattr(
        'ccbd.start_flow.TmuxCleanupHistoryStore',
        lambda paths: SimpleNamespace(append=lambda event: history_events.append(event)),
    )
    monkeypatch.setattr('ccbd.start_flow.resolve_agent_binding', lambda **kwargs: None)
    monkeypatch.setattr(
        'ccbd.start_flow.ensure_agent_runtime',
        lambda *args, **kwargs: RuntimeLaunchResult(
            launched=True,
            binding=AgentBinding(
                runtime_ref='tmux:%55',
                session_ref='session-55',
                provider='codex',
                runtime_root=str(app.paths.agent_provider_runtime_dir('demo', 'codex')),
                runtime_pid=55,
                session_file=str(project_root / '.ccb' / '.codex-demo-session'),
                session_id='session-55',
                tmux_socket_name=None,
                tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
                terminal='tmux',
                pane_id='%55',
                active_pane_id='%55',
                pane_title_marker='CCB-demo',
                pane_state='alive',
            ),
        ),
    )

    summary = app.runtime_supervisor.start(
        agent_names=('demo',),
        restore=False,
        auto_permission=False,
        cleanup_tmux_orphans=True,
        interactive_tmux_layout=True,
    )

    assert summary.started == ('demo',)
    assert cleanup_calls == [
        {
            'project_id': app.project_id,
            'active_panes_by_socket': {str(app.paths.ccbd_tmux_socket_path): ('%0', '%55')},
        }
    ]
    assert len(history_events) == 1
    assert 'cleanup_tmux_orphans:killed=1' in summary.actions_taken
    assert 'cleanup_tmux_orphans:skipped_project_namespace' not in summary.actions_taken


def test_runtime_supervisor_reuses_agent_only_binding_without_cmd_namespace_match(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-agent-only-binding'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)
    monkeypatch.setattr(
        app.project_namespace,
        'ensure',
        lambda: SimpleNamespace(
            tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
            tmux_session_name=app.paths.ccbd_tmux_session_name,
            namespace_epoch=6,
        ),
    )
    monkeypatch.setattr('ccbd.start_flow.TmuxBackend', _FakeNamespaceTmuxBackend)
    monkeypatch.setattr('ccbd.start_flow.set_tmux_ui_active', lambda active: None)
    layout_targets: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        'ccbd.start_flow.prepare_tmux_start_layout',
        lambda context, config, targets, **kwargs: layout_targets.append(tuple(targets)) or SimpleNamespace(cmd_pane_id=None, agent_panes={}),
    )
    monkeypatch.setattr('ccbd.start_flow.cleanup_project_tmux_orphans_by_socket', lambda **kwargs: ())
    monkeypatch.setattr(
        'ccbd.start_flow.TmuxCleanupHistoryStore',
        lambda paths: SimpleNamespace(append=lambda event: None),
    )
    monkeypatch.setattr(
        'ccbd.start_flow.resolve_agent_binding',
        lambda **kwargs: AgentBinding(
            runtime_ref='tmux:%9',
            session_ref='demo-session-id',
            provider='codex',
            runtime_root=str(app.paths.agent_provider_runtime_dir('demo', 'codex')),
            runtime_pid=9,
            session_file=str(project_root / '.ccb' / '.codex-demo-session'),
            session_id='demo-session-id',
            tmux_socket_name=None,
            tmux_socket_path=None,
            terminal='tmux',
            pane_id='%9',
            active_pane_id='%9',
            pane_title_marker='CCB-demo',
            pane_state='unknown',
        ),
    )
    monkeypatch.setattr(
        'ccbd.start_flow.ensure_agent_runtime',
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('agent-only startup should reuse existing binding')),
    )

    summary = app.runtime_supervisor.start(
        agent_names=('demo',),
        restore=False,
        auto_permission=False,
        cleanup_tmux_orphans=False,
        interactive_tmux_layout=True,
    )

    runtime = app.registry.get('demo')
    assert summary.started == ('demo',)
    assert layout_targets == [()]
    assert 'reuse_binding:demo' in summary.actions_taken
    assert runtime is not None
    assert runtime.runtime_ref == 'tmux:%9'
    assert runtime.session_ref == 'demo-session-id'


def test_runtime_supervisor_project_namespace_start_does_not_preheal_dead_binding_before_layout(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-layout-launch'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('cmd; demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)
    monkeypatch.setattr(
        app.project_namespace,
        'ensure',
        lambda: SimpleNamespace(
            tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
            tmux_session_name=app.paths.ccbd_tmux_session_name,
            namespace_epoch=4,
        ),
    )
    monkeypatch.setattr('ccbd.start_flow.TmuxBackend', _FakeNamespaceTmuxBackend)
    monkeypatch.setattr('ccbd.start_flow.set_tmux_ui_active', lambda active: None)
    monkeypatch.setattr('ccbd.start_flow.cleanup_project_tmux_orphans_by_socket', lambda **kwargs: ())
    monkeypatch.setattr(
        'ccbd.start_flow.TmuxCleanupHistoryStore',
        lambda paths: SimpleNamespace(append=lambda event: None),
    )

    layout_targets: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        'ccbd.start_flow.prepare_tmux_start_layout',
        lambda context, config, targets, **kwargs: layout_targets.append(tuple(targets)) or SimpleNamespace(cmd_pane_id='%0', agent_panes={'demo': '%2'}),
    )

    def _resolve_agent_binding(**kwargs):
        if kwargs.get('ensure_usable') is not False:
            raise AssertionError('project namespace startup should not call ensure_usable=True before layout assignment')
        return AgentBinding(
            runtime_ref='tmux:%41',
            session_ref='session-41',
            provider='codex',
            runtime_root=str(app.paths.agent_provider_runtime_dir('demo', 'codex')),
            runtime_pid=41,
            session_file=str(project_root / '.ccb' / '.codex-demo-session'),
            session_id='session-41',
            tmux_socket_name='sock-a',
            tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
            terminal='tmux',
            pane_id='%41',
            active_pane_id=None,
            pane_title_marker='CCB-demo',
            pane_state='dead',
        )

    monkeypatch.setattr('ccbd.start_flow.resolve_agent_binding', _resolve_agent_binding)
    launch_binding_hints: list[object | None] = []
    monkeypatch.setattr(
        'ccbd.start_flow.ensure_agent_runtime',
        lambda *args, **kwargs: launch_binding_hints.append(args[4]) or RuntimeLaunchResult(
            launched=True,
            binding=AgentBinding(
                runtime_ref='tmux:%55',
                session_ref='session-55',
                provider='codex',
                runtime_root=str(app.paths.agent_provider_runtime_dir('demo', 'codex')),
                runtime_pid=55,
                session_file=str(project_root / '.ccb' / '.codex-demo-session'),
                session_id='session-55',
                tmux_socket_name='sock-a',
                tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
                terminal='tmux',
                pane_id='%55',
                active_pane_id='%55',
                pane_title_marker='CCB-demo',
                pane_state='alive',
            ),
        ),
    )

    summary = app.runtime_supervisor.start(
        agent_names=('demo',),
        restore=False,
        auto_permission=False,
        cleanup_tmux_orphans=False,
        interactive_tmux_layout=True,
    )

    assert summary.started == ('demo',)
    assert layout_targets == [('demo',)]
    assert launch_binding_hints == [None]
    assert 'prepare_tmux_layout:demo' in summary.actions_taken


def test_ccbd_start_marks_project_mounted_before_socket_listen(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-start-order'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)
    observed: dict[str, object] = {}

    def fake_listen() -> None:
        observed['lease_during_listen'] = app.mount_manager.load_state()
        app.paths.ccbd_socket_path.parent.mkdir(parents=True, exist_ok=True)
        app.paths.ccbd_socket_path.touch()

    monkeypatch.setattr(app.socket_server, 'listen', fake_listen)
    monkeypatch.setattr(app.dispatcher, 'restore_running_jobs', lambda: None)
    monkeypatch.setattr(app.dispatcher, 'last_restore_report', lambda **kwargs: None)
    monkeypatch.setattr(app.restore_report_store, 'save', lambda report: None)

    lease = app.start()
    mounted_during_listen = observed.get('lease_during_listen')

    assert mounted_during_listen is not None
    assert mounted_during_listen.mount_state.value == 'mounted'
    assert mounted_during_listen.generation == lease.generation
    assert app.mount_manager.load_state().mount_state.value == 'mounted'

    app.request_shutdown()


def test_ccbd_start_rolls_back_mount_when_restore_fails(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-start-rollback'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)

    def fake_listen() -> None:
        app.paths.ccbd_socket_path.parent.mkdir(parents=True, exist_ok=True)
        app.paths.ccbd_socket_path.touch()

    monkeypatch.setattr(app.socket_server, 'listen', fake_listen)
    monkeypatch.setattr(app.dispatcher, 'restore_running_jobs', lambda: (_ for _ in ()).throw(RuntimeError('boom')))

    with pytest.raises(RuntimeError, match='boom'):
        app.start()

    lease = app.mount_manager.load_state()
    assert lease is not None
    assert lease.mount_state.value == 'unmounted'
    assert not app.paths.ccbd_socket_path.exists()


def test_ccbd_start_records_startup_report_before_return(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-start-report-before-return'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)

    monkeypatch.setattr(app.socket_server, 'listen', lambda: None)
    monkeypatch.setattr(app.dispatcher, 'restore_running_jobs', lambda: None)
    monkeypatch.setattr(app.dispatcher, 'last_restore_report', lambda **kwargs: None)
    monkeypatch.setattr(app.restore_report_store, 'save', lambda report: None)

    lease = app.start()
    report = CcbdStartupReportStore(app.paths).load()

    assert lease is not None
    assert report is not None
    assert report.status == 'ok'
    assert report.actions_taken == ('mount_backend', 'listen_socket', 'restore_running_jobs')
    assert app._startup_completed is True

    app.request_shutdown()


def test_ccbd_serve_forever_defers_restore_until_socket_loop_tick(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-serve-forever-startup-tick'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    monkeypatch.delenv('CCB_EXPERIMENTAL_WINDOWS_NATIVE', raising=False)
    monkeypatch.delenv('CCB_IPC_KIND', raising=False)
    app = CcbdApp(project_root)
    events: list[str] = []

    monkeypatch.setattr(app.socket_server, 'listen', lambda: events.append('listen'))
    monkeypatch.setattr(app.dispatcher, 'restore_running_jobs', lambda: events.append('restore'))
    monkeypatch.setattr(app.dispatcher, 'last_restore_report', lambda **kwargs: None)
    monkeypatch.setattr(app.restore_report_store, 'save', lambda report: events.append('save_restore_report'))
    monkeypatch.setattr(app, 'heartbeat', lambda: events.append('heartbeat') or app.lease)
    monkeypatch.setattr(app.socket_server, 'shutdown', lambda: events.append('shutdown'))

    def fake_serve_forever(*, poll_interval: float, on_tick):
        assert poll_interval == 0.05
        events.append('serve_forever')
        assert events == ['listen', 'serve_forever']
        assert CcbdStartupReportStore(app.paths).load() is None
        on_tick()
        events.append('after_tick')

    monkeypatch.setattr(app.socket_server, 'serve_forever', fake_serve_forever)

    app.serve_forever(poll_interval=0.05)

    report = CcbdStartupReportStore(app.paths).load()

    assert report is not None
    assert report.status == 'ok'
    assert report.actions_taken == ('mount_backend', 'listen_socket', 'restore_running_jobs')
    assert events == ['listen', 'serve_forever', 'restore', 'heartbeat', 'after_tick', 'shutdown']
    assert app._startup_completed is False


def test_ccbd_serve_forever_completes_startup_before_socket_loop_for_named_pipe(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-serve-forever-named-pipe-startup'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    monkeypatch.setenv('CCB_EXPERIMENTAL_WINDOWS_NATIVE', '1')
    monkeypatch.setenv('CCB_IPC_KIND', 'named_pipe')
    app = CcbdApp(project_root)
    events: list[str] = []

    monkeypatch.setattr(app.socket_server, 'listen', lambda: events.append('listen'))
    monkeypatch.setattr(app.dispatcher, 'restore_running_jobs', lambda: events.append('restore'))
    monkeypatch.setattr(app.dispatcher, 'last_restore_report', lambda **kwargs: None)
    monkeypatch.setattr(app.restore_report_store, 'save', lambda report: events.append('save_restore_report'))
    monkeypatch.setattr(app, 'heartbeat', lambda: events.append('heartbeat') or app.lease)
    monkeypatch.setattr(app.socket_server, 'shutdown', lambda: events.append('shutdown'))

    def fake_serve_forever(*, poll_interval: float, on_tick):
        assert poll_interval == 0.05
        events.append('serve_forever')
        report = CcbdStartupReportStore(app.paths).load()
        assert report is not None
        assert report.actions_taken == ('mount_backend', 'listen_socket', 'restore_running_jobs')
        assert events == ['listen', 'restore', 'serve_forever']
        on_tick()
        events.append('after_tick')

    monkeypatch.setattr(app.socket_server, 'serve_forever', fake_serve_forever)

    app.serve_forever(poll_interval=0.05)

    report = CcbdStartupReportStore(app.paths).load()

    assert report is not None
    assert report.status == 'ok'
    assert report.actions_taken == ('mount_backend', 'listen_socket', 'restore_running_jobs')
    assert events == ['listen', 'restore', 'serve_forever', 'heartbeat', 'after_tick', 'shutdown']
    assert app._startup_completed is False


def test_ccbd_start_runs_restore_again_after_request_shutdown(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-start-repeat'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)
    events: list[str] = []

    monkeypatch.setattr(app.socket_server, 'listen', lambda: events.append('listen'))
    monkeypatch.setattr(app.socket_server, 'shutdown', lambda: events.append('shutdown'))
    monkeypatch.setattr(app.dispatcher, 'restore_running_jobs', lambda: events.append('restore'))
    monkeypatch.setattr(app.dispatcher, 'last_restore_report', lambda **kwargs: None)
    monkeypatch.setattr(app.restore_report_store, 'save', lambda report: events.append('save_restore_report'))

    first = app.start()
    app.request_shutdown()
    second = app.start()

    report = CcbdStartupReportStore(app.paths).load()

    assert first is not None
    assert second is not None
    assert events == ['listen', 'restore', 'shutdown', 'listen', 'restore']
    assert report is not None
    assert report.status == 'ok'
    assert app._startup_completed is True

    app.request_shutdown()


def test_ccbd_serve_forever_runs_startup_tick_again_after_request_shutdown(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-ccbd-serve-forever-repeat'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    app = CcbdApp(project_root)
    events: list[str] = []

    monkeypatch.setattr(app.socket_server, 'listen', lambda: events.append('listen'))
    monkeypatch.setattr(app.dispatcher, 'restore_running_jobs', lambda: events.append('restore'))
    monkeypatch.setattr(app.dispatcher, 'last_restore_report', lambda **kwargs: None)
    monkeypatch.setattr(app.restore_report_store, 'save', lambda report: events.append('save_restore_report'))
    monkeypatch.setattr(app, 'heartbeat', lambda: events.append('heartbeat') or app.lease)
    monkeypatch.setattr(app.socket_server, 'shutdown', lambda: events.append('shutdown'))

    def fake_serve_forever(*, poll_interval: float, on_tick):
        assert poll_interval == 0.05
        events.append('serve_forever')
        on_tick()
        events.append('after_tick')

    monkeypatch.setattr(app.socket_server, 'serve_forever', fake_serve_forever)

    app.serve_forever(poll_interval=0.05)
    app.serve_forever(poll_interval=0.05)

    report = CcbdStartupReportStore(app.paths).load()

    assert report is not None
    assert report.status == 'ok'
    assert events == [
        'listen',
        'serve_forever',
        'restore',
        'heartbeat',
        'after_tick',
        'shutdown',
        'listen',
        'serve_forever',
        'restore',
        'heartbeat',
        'after_tick',
        'shutdown',
    ]
    assert app._startup_completed is False
