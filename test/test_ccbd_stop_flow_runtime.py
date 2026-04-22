from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from agents.models import AgentRuntime, AgentState
from agents.store import AgentRuntimeStore
from ccbd.models import CcbdRuntimeSnapshot, CcbdShutdownReport
from ccbd.handlers.shutdown import build_shutdown_handler
from ccbd.handlers.stop_all import build_stop_all_handler
from ccbd.lifecycle_report_store import CcbdShutdownReportStore
from ccbd.services.mount import MountManager
from ccbd.services.ownership import OwnershipGuard
from ccbd.stop_flow_runtime.service import stop_all_project
from ccbd.stop_flow_runtime.pid_cleanup import collect_pid_candidates
from ccbd.stop_flow_runtime.pid_cleanup import collect_project_process_candidates
from ccbd.stop_flow_runtime.pid_cleanup import runtime_job_id
from ccbd.stop_flow_runtime.pid_cleanup import runtime_job_owner_pid
from ccbd.stop_flow_runtime.pid_cleanup import terminate_runtime_pids
from ccbd.stop_flow_runtime.models import StopAllSummary
from runtime_pid_cleanup.process_tree_owner import ProcessTreeTarget
from ccbd.stop_flow_runtime.runtime_records import build_shutdown_runtime_snapshots, extra_agent_dir_names
from storage.paths import PathLayout


def _bound_runtime(agent_name: str, *, project_id: str, workspace_path: str, pid: int) -> AgentRuntime:
    return AgentRuntime(
        agent_name=agent_name,
        state=AgentState.IDLE,
        pid=pid,
        started_at='2026-03-18T00:00:00Z',
        last_seen_at='2026-03-18T00:00:00Z',
        runtime_ref=f'psmux:%{pid}',
        session_ref=f'{agent_name}-session',
        workspace_path=workspace_path,
        project_id=project_id,
        backend_type='pane-backed',
        queue_depth=0,
        socket_path=None,
        health='healthy',
        provider='codex',
        runtime_root=f'C:/runtime/{agent_name}',
        runtime_pid=pid + 1000,
        job_id=f'job-{agent_name}',
        job_owner_pid=pid + 2000,
        terminal_backend='psmux',
        pane_id=f'%{pid}',
        active_pane_id=f'%{pid}',
        pane_title_marker=f'CCB-{agent_name}',
        pane_state='alive',
        tmux_socket_name=f'psmux-{agent_name}',
        tmux_socket_path=rf'\\.\pipe\psmux-{agent_name}',
        session_file=f'C:/sessions/{agent_name}.json',
        session_id=f'{agent_name}-session-id',
        desired_state='mounted',
        reconcile_state='stable',
    )


def _prepare_app(project_root: Path) -> SimpleNamespace:
    project_root.mkdir(parents=True, exist_ok=True)
    paths = PathLayout(project_root)
    runtime = _bound_runtime(
        'demo',
        project_id='proj-1',
        workspace_path=str(paths.workspace_path('demo')),
        pid=777,
    )
    registry = SimpleNamespace(
        get=lambda agent_name: runtime if agent_name == 'demo' else None,
        list_known_agents=lambda: ('demo',),
    )
    mount_manager = MountManager(
        paths,
        clock=lambda: '2026-04-08T00:00:00Z',
        uid_getter=lambda: 1000,
        boot_id_getter=lambda: 'boot-1',
    )
    ownership_guard = OwnershipGuard(
        paths,
        mount_manager,
        clock=lambda: '2026-04-08T00:00:00Z',
        pid_exists=lambda pid: True,
        socket_probe=lambda path, ipc_kind=None: True,
        current_pid=222,
    )
    app = SimpleNamespace(
        paths=paths,
        config=SimpleNamespace(agents={'demo': object()}),
        registry=registry,
        project_id='proj-1',
        clock=lambda: '2026-04-08T00:00:00Z',
        mount_manager=mount_manager,
        ownership_guard=ownership_guard,
        shutdown_report_store=CcbdShutdownReportStore(paths),
        lease=None,
        runtime_supervisor=None,
    )

    def _request_shutdown():
        app.lease = app.mount_manager.mark_unmounted()

    app.request_shutdown = _request_shutdown
    app.lease = app.mount_manager.mark_mounted(
        project_id=app.project_id,
        pid=111,
        socket_path=app.paths.ccbd_ipc_ref,
        ipc_kind=app.paths.ccbd_ipc_kind,
        generation=3,
        backend_family='tmux',
        backend_impl='psmux',
    )
    return app


def test_extra_agent_dir_names_skips_configured_names(tmp_path: Path) -> None:
    agents_dir = tmp_path / '.ccb' / 'agents'
    (agents_dir / 'agent1').mkdir(parents=True)
    (agents_dir / 'cmd').mkdir(parents=True)
    (agents_dir / 'agent5').mkdir(parents=True)
    (agents_dir / 'not-a-dir.txt').write_text('x', encoding='utf-8')

    paths = SimpleNamespace(agents_dir=agents_dir)

    assert extra_agent_dir_names(paths, ('agent1', 'cmd')) == ('agent5',)


def test_build_shutdown_runtime_snapshots_prefers_live_registry_runtime_for_configured_agent(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-shutdown-runtime-snapshots'
    project_root.mkdir(parents=True, exist_ok=True)
    paths = PathLayout(project_root)
    stale_runtime = AgentRuntime(
        agent_name='demo',
        state=AgentState.STOPPED,
        pid=None,
        started_at='2026-04-01T00:00:00Z',
        last_seen_at='2026-04-01T00:00:00Z',
        runtime_ref='stale-runtime',
        session_ref='stale-session',
        workspace_path=str(paths.workspace_path('demo')),
        project_id='proj-1',
        backend_type='pane-backed',
        queue_depth=0,
        socket_path=None,
        health='stopped',
        provider='codex',
        runtime_root='C:/stale-runtime-root',
        runtime_pid=111,
        job_id='job-stale',
        job_owner_pid=222,
        terminal_backend='tmux',
        session_file='C:/stale.session.json',
        session_id='session-stale',
    )
    AgentRuntimeStore(paths).save(stale_runtime)
    live_runtime = AgentRuntime(
        agent_name='demo',
        state=AgentState.IDLE,
        pid=333,
        started_at='2026-04-01T00:00:00Z',
        last_seen_at='2026-04-01T00:00:00Z',
        runtime_ref='psmux:%7',
        session_ref='session-live',
        workspace_path=str(paths.workspace_path('demo')),
        project_id='proj-1',
        backend_type='pane-backed',
        queue_depth=0,
        socket_path=None,
        health='healthy',
        provider='codex',
        runtime_root='C:/live-runtime-root',
        runtime_pid=4321,
        job_id='job-live',
        job_owner_pid=654,
        terminal_backend='psmux',
        session_file='C:/live.session.json',
        session_id='session-live',
    )

    snapshots = build_shutdown_runtime_snapshots(
        paths=paths,
        config=SimpleNamespace(agents={'demo': object()}),
        registry=SimpleNamespace(
            get=lambda agent_name: live_runtime,
            list_known_agents=lambda: ('demo',),
        ),
    )

    assert len(snapshots) == 1
    assert snapshots[0].runtime_ref == 'psmux:%7'
    assert snapshots[0].session_id == 'session-live'
    assert snapshots[0].runtime_root == 'C:/live-runtime-root'
    assert snapshots[0].runtime_pid == 4321
    assert snapshots[0].job_id == 'job-live'
    assert snapshots[0].job_owner_pid == 654


def test_shutdown_handler_writes_runtime_snapshots_from_live_registry_runtime(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-shutdown-handler-runtime-snapshots'
    app = _prepare_app(project_root)

    result = build_shutdown_handler(app)({})
    report = app.shutdown_report_store.load()

    assert result['state'] == 'unmounted'
    assert result['generation'] == 3
    assert report is not None
    assert report.trigger == 'shutdown'
    assert len(report.runtime_snapshots) == 1
    assert report.runtime_snapshots[0].runtime_ref == 'psmux:%777'
    assert report.runtime_snapshots[0].session_id == 'demo-session-id'
    assert report.runtime_snapshots[0].runtime_root == 'C:/runtime/demo'
    assert report.runtime_snapshots[0].runtime_pid == 1777
    assert report.runtime_snapshots[0].job_id == 'job-demo'
    assert report.runtime_snapshots[0].job_owner_pid == 2777


def test_stop_all_handler_writes_runtime_snapshots_when_prior_report_missing(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-stop-all-handler-runtime-snapshots'
    app = _prepare_app(project_root)
    runtime = _bound_runtime(
        'demo',
        project_id=app.project_id,
        workspace_path=str(app.paths.workspace_path('demo')),
        pid=701,
    )
    app.registry = SimpleNamespace(
        get=lambda agent_name: runtime if agent_name == 'demo' else None,
        list_known_agents=lambda: ('demo',),
    )
    app.lease = app.mount_manager.mark_mounted(
        project_id=app.project_id,
        pid=111,
        socket_path=app.paths.ccbd_ipc_ref,
        ipc_kind=app.paths.ccbd_ipc_kind,
        generation=4,
        backend_family='tmux',
        backend_impl='psmux',
    )
    app.runtime_supervisor = SimpleNamespace(
        stop_all=lambda *, force: StopAllSummary(
            project_id=app.project_id,
            state='unmounted',
            socket_path=str(app.paths.ccbd_socket_path),
            forced=force,
            stopped_agents=('demo',),
            cleanup_summaries=(),
        )
    )
    result = build_stop_all_handler(app)({'force': False})
    report = app.shutdown_report_store.load()

    assert result['stopped_agents'] == ['demo']
    assert report is not None
    assert report.trigger == 'stop_all'
    assert len(report.runtime_snapshots) == 1
    assert report.runtime_snapshots[0].runtime_ref == 'psmux:%701'
    assert report.runtime_snapshots[0].session_id == 'demo-session-id'
    assert report.runtime_snapshots[0].runtime_root == 'C:/runtime/demo'
    assert report.runtime_snapshots[0].runtime_pid == 1701
    assert report.runtime_snapshots[0].job_id == 'job-demo'
    assert report.runtime_snapshots[0].job_owner_pid == 2701


def test_stop_all_handler_preserves_prior_runtime_snapshots_when_report_exists(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-stop-all-handler-preserves-prior-snapshots'
    app = _prepare_app(project_root)
    current_runtime = _bound_runtime(
        'demo',
        project_id=app.project_id,
        workspace_path=str(app.paths.workspace_path('demo')),
        pid=888,
    )
    app.registry = SimpleNamespace(
        get=lambda agent_name: current_runtime if agent_name == 'demo' else None,
        list_known_agents=lambda: ('demo',),
    )
    prior_runtime = _bound_runtime(
        'demo',
        project_id=app.project_id,
        workspace_path=str(app.paths.workspace_path('demo')),
        pid=555,
    )
    app.shutdown_report_store.save(
        CcbdShutdownReport(
            project_id=app.project_id,
            generated_at='2026-04-08T00:00:00Z',
            trigger='shutdown',
            status='ok',
            forced=False,
            stopped_agents=(),
            daemon_generation=2,
            reason='shutdown',
            inspection_after={},
            actions_taken=('request_shutdown',),
            cleanup_summaries=(),
            runtime_snapshots=(CcbdRuntimeSnapshot.from_runtime(prior_runtime),),
            failure_reason=None,
        )
    )
    app.runtime_supervisor = SimpleNamespace(
        stop_all=lambda *, force: StopAllSummary(
            project_id=app.project_id,
            state='unmounted',
            socket_path=str(app.paths.ccbd_socket_path),
            forced=force,
            stopped_agents=('demo',),
            cleanup_summaries=(),
        )
    )

    build_stop_all_handler(app)({'force': False})
    report = app.shutdown_report_store.load()

    assert report is not None
    assert len(report.runtime_snapshots) == 1
    assert report.runtime_snapshots[0].runtime_ref == 'psmux:%555'
    assert report.runtime_snapshots[0].runtime_pid == 1555
    assert report.runtime_snapshots[0].job_id == 'job-demo'
    assert report.actions_taken == ('request_shutdown', 'request_shutdown')


def test_collect_pid_candidates_uses_runtime_root_and_force_fallback(tmp_path: Path) -> None:
    agent_dir = tmp_path / '.ccb' / 'agents' / 'agent1'
    provider_runtime_dir = agent_dir / 'provider-runtime' / 'codex'
    provider_runtime_dir.mkdir(parents=True)
    (provider_runtime_dir / 'fallback.pid').write_text('456\n', encoding='utf-8')

    dedicated_runtime_root = tmp_path / 'runtime-root'
    dedicated_runtime_root.mkdir()
    (dedicated_runtime_root / 'codex.pid').write_text('789\n', encoding='utf-8')

    runtime = SimpleNamespace(runtime_pid=123, pid=None, runtime_root=str(dedicated_runtime_root))
    candidates = collect_pid_candidates(agent_dir, runtime=runtime, fallback_to_agent_dir=True)

    assert candidates[123] == [agent_dir / 'runtime.json']
    assert candidates[456] == [provider_runtime_dir / 'fallback.pid']
    assert candidates[789] == [dedicated_runtime_root / 'codex.pid']


def test_runtime_job_metadata_falls_back_to_nested_provider_runtime_without_runtime_record(tmp_path: Path) -> None:
    agent_dir = tmp_path / '.ccb' / 'agents' / 'legacy'
    provider_runtime_dir = agent_dir / 'provider-runtime' / 'codex'
    provider_runtime_dir.mkdir(parents=True)
    (provider_runtime_dir / 'bridge.pid').write_text('456\n', encoding='utf-8')
    (provider_runtime_dir / 'job.id').write_text('job-object-legacy\n', encoding='utf-8')

    assert runtime_job_owner_pid(agent_dir, runtime=None, fallback_to_agent_dir=False) == 456
    assert runtime_job_id(agent_dir, runtime=None, fallback_to_agent_dir=False) == 'job-object-legacy'


def test_collect_project_process_candidates_matches_ccb_runtime_cmdline(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    ccb_root = project_root / '.ccb'
    proc_root = tmp_path / 'proc'
    for pid in ('101', '202', '303'):
        (proc_root / pid).mkdir(parents=True)

    mapping = {
        101: f'python -m provider_backends.codex.bridge --runtime-dir {ccb_root / "agents/agent1/provider-runtime/codex"}',
        202: f'tmux -S {ccb_root / "ccbd/tmux.sock"} new-session -d',
        303: 'python unrelated.py',
    }

    candidates = collect_project_process_candidates(
        project_root,
        proc_root=proc_root,
        read_proc_cmdline_fn=lambda pid: mapping.get(pid, ''),
        current_pid=999999,
    )

    assert sorted(candidates) == [101, 202]
    assert candidates[101] == [ccb_root]
    assert candidates[202] == [ccb_root]


def test_terminate_runtime_pids_includes_project_process_scan(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo'
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        'ccbd.stop_flow_runtime.pid_cleanup._terminate_runtime_pids_impl',
        lambda **kwargs: seen.update(kwargs),
    )
    monkeypatch.setattr(
        'ccbd.stop_flow_runtime.pid_cleanup.collect_project_process_candidates',
        lambda project_root: {321: [project_root / '.ccb']},
    )

    terminate_runtime_pids(
        project_root=project_root,
        pid_candidates={123: [project_root / 'hint.pid']},
        priority_pids=(999,),
    )

    collect_fn = seen['collect_project_process_candidates_fn']
    assert collect_fn(project_root) == {321: [project_root / '.ccb']}
    assert seen['pid_candidates'] == {123: [project_root / 'hint.pid']}
    assert seen['priority_pids'] == (999,)


def test_stop_flow_pid_cleanup_uses_windows_job_metadata_owner_factory(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo'
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        'ccbd.stop_flow_runtime.pid_cleanup._terminate_runtime_pids_impl',
        lambda **kwargs: seen.update(kwargs),
    )

    terminate_runtime_pids(
        project_root=project_root,
        pid_candidates={123: [project_root / 'hint.pid']},
        pid_metadata={123: {'job_id': 'job-object-1', 'job_owner_pid': 123}},
    )

    owner_factory = seen['process_tree_owner_factory']
    selected = owner_factory.build(
        ProcessTreeTarget(
            pid=123,
            hint_paths=(project_root / 'hint.pid',),
            metadata={'job_id': 'job-object-1', 'job_owner_pid': 123},
        )
    )

    assert selected is not None


def test_stop_all_project_prioritizes_job_owner_pid_before_runtime_children(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-stop-all-job-owner'
    project_root.mkdir(parents=True, exist_ok=True)
    paths = PathLayout(project_root)
    runtime_dir = paths.agent_provider_runtime_dir('demo', 'codex')
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / 'bridge.pid').write_text('111\n', encoding='utf-8')
    (runtime_dir / 'codex.pid').write_text('222\n', encoding='utf-8')
    runtime = AgentRuntime(
        agent_name='demo',
        state=AgentState.IDLE,
        pid=333,
        started_at='2026-04-01T00:00:00Z',
        last_seen_at='2026-04-01T00:00:00Z',
        runtime_ref='tmux:%1',
        session_ref='session-ref',
        workspace_path=str(paths.workspace_path('demo')),
        project_id='proj-1',
        backend_type='pane-backed',
        queue_depth=0,
        socket_path=None,
        health='healthy',
        provider='codex',
        job_id='job-object-1',
        job_owner_pid=999,
    )

    live_pids = {111, 222, 333, 999}
    terminated: list[int] = []

    def _terminate(pid, timeout_s, is_pid_alive_fn):
        terminated.append(pid)
        if pid == 999:
            live_pids.clear()
        else:
            live_pids.discard(pid)
        return True

    monkeypatch.setattr('ccbd.stop_flow_runtime.pid_cleanup.is_pid_alive', lambda pid: pid in live_pids)
    monkeypatch.setattr('ccbd.stop_flow_runtime.pid_cleanup.pid_matches_project', lambda pid, project_root, hint_paths: True)
    monkeypatch.setattr('ccbd.stop_flow_runtime.pid_cleanup.terminate_pid_tree', _terminate)

    execution = stop_all_project(
        project_root=project_root,
        project_id='proj-1',
        paths=paths,
        registry=SimpleNamespace(
            list_known_agents=lambda: ('demo',),
            get=lambda agent_name: runtime,
            upsert=lambda updated: updated,
        ),
        project_namespace=None,
        clock=lambda: '2026-04-06T00:00:00Z',
        force=False,
        cleanup_project_tmux_orphans_by_socket_fn=lambda **kwargs: (),
        tmux_cleanup_history_store_cls=lambda paths: type('Store', (), {'append': staticmethod(lambda event: None)})(),
    )

    assert terminated == [999]
    assert execution.summary.state == 'unmounted'


def test_stop_all_project_prioritizes_bridge_pid_when_job_owner_pid_missing(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-stop-all-bridge-owner'
    project_root.mkdir(parents=True, exist_ok=True)
    paths = PathLayout(project_root)
    runtime_dir = paths.agent_provider_runtime_dir('demo', 'codex')
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / 'bridge.pid').write_text('111\n', encoding='utf-8')
    (runtime_dir / 'codex.pid').write_text('222\n', encoding='utf-8')
    runtime = AgentRuntime(
        agent_name='demo',
        state=AgentState.IDLE,
        pid=333,
        started_at='2026-04-01T00:00:00Z',
        last_seen_at='2026-04-01T00:00:00Z',
        runtime_ref='tmux:%1',
        session_ref='session-ref',
        workspace_path=str(paths.workspace_path('demo')),
        project_id='proj-1',
        backend_type='pane-backed',
        queue_depth=0,
        socket_path=None,
        health='healthy',
        provider='codex',
    )

    live_pids = {111, 222, 333}
    terminated: list[int] = []

    def _terminate(pid, timeout_s, is_pid_alive_fn):
        terminated.append(pid)
        if pid == 111:
            live_pids.clear()
        else:
            live_pids.discard(pid)
        return True

    monkeypatch.setattr('ccbd.stop_flow_runtime.pid_cleanup.is_pid_alive', lambda pid: pid in live_pids)
    monkeypatch.setattr('ccbd.stop_flow_runtime.pid_cleanup.pid_matches_project', lambda pid, project_root, hint_paths: True)
    monkeypatch.setattr('ccbd.stop_flow_runtime.pid_cleanup.terminate_pid_tree', _terminate)

    execution = stop_all_project(
        project_root=project_root,
        project_id='proj-1',
        paths=paths,
        registry=SimpleNamespace(
            list_known_agents=lambda: ('demo',),
            get=lambda agent_name: runtime,
            upsert=lambda updated: updated,
        ),
        project_namespace=None,
        clock=lambda: '2026-04-06T00:00:00Z',
        force=False,
        cleanup_project_tmux_orphans_by_socket_fn=lambda **kwargs: (),
        tmux_cleanup_history_store_cls=lambda paths: type('Store', (), {'append': staticmethod(lambda event: None)})(),
    )

    assert terminated == [111]
    assert execution.summary.state == 'unmounted'


def test_stop_all_project_passes_pid_job_metadata_to_cleanup(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-stop-all-job-metadata'
    project_root.mkdir(parents=True, exist_ok=True)
    paths = PathLayout(project_root)
    runtime_dir = paths.agent_provider_runtime_dir('demo', 'codex')
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / 'bridge.pid').write_text('111\n', encoding='utf-8')
    (runtime_dir / 'codex.pid').write_text('222\n', encoding='utf-8')
    runtime = AgentRuntime(
        agent_name='demo',
        state=AgentState.IDLE,
        pid=333,
        started_at='2026-04-01T00:00:00Z',
        last_seen_at='2026-04-01T00:00:00Z',
        runtime_ref='tmux:%1',
        session_ref='session-ref',
        workspace_path=str(paths.workspace_path('demo')),
        project_id='proj-1',
        backend_type='pane-backed',
        queue_depth=0,
        socket_path=None,
        health='healthy',
        provider='codex',
        job_id='job-object-1',
        job_owner_pid=111,
    )
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        'ccbd.stop_flow_runtime.service.terminate_runtime_pids',
        lambda **kwargs: seen.update(kwargs),
    )

    stop_all_project(
        project_root=project_root,
        project_id='proj-1',
        paths=paths,
        registry=SimpleNamespace(
            list_known_agents=lambda: ('demo',),
            get=lambda agent_name: runtime,
            upsert=lambda updated: updated,
        ),
        project_namespace=None,
        clock=lambda: '2026-04-06T00:00:00Z',
        force=False,
        cleanup_project_tmux_orphans_by_socket_fn=lambda **kwargs: (),
        tmux_cleanup_history_store_cls=lambda paths: type('Store', (), {'append': staticmethod(lambda event: None)})(),
    )

    assert seen['pid_metadata'][111]['job_id'] == 'job-object-1'
    assert seen['pid_metadata'][111]['job_owner_pid'] == 111
    assert seen['pid_metadata'][222]['job_id'] == 'job-object-1'
    assert seen['pid_metadata'][222]['job_owner_pid'] == 111


def test_stop_all_project_recovers_job_metadata_from_extra_agent_runtime_without_runtime_record(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-stop-all-extra-agent-job-metadata'
    project_root.mkdir(parents=True, exist_ok=True)
    paths = PathLayout(project_root)
    legacy_runtime_dir = paths.agent_provider_runtime_dir('legacy', 'codex')
    legacy_runtime_dir.mkdir(parents=True, exist_ok=True)
    (legacy_runtime_dir / 'bridge.pid').write_text('111\n', encoding='utf-8')
    (legacy_runtime_dir / 'codex.pid').write_text('222\n', encoding='utf-8')
    (legacy_runtime_dir / 'job.id').write_text('job-object-legacy\n', encoding='utf-8')
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        'ccbd.stop_flow_runtime.service.terminate_runtime_pids',
        lambda **kwargs: seen.update(kwargs),
    )

    stop_all_project(
        project_root=project_root,
        project_id='proj-1',
        paths=paths,
        registry=SimpleNamespace(
            list_known_agents=lambda: (),
            get=lambda agent_name: None,
            upsert=lambda updated: updated,
        ),
        project_namespace=None,
        clock=lambda: '2026-04-06T00:00:00Z',
        force=False,
        cleanup_project_tmux_orphans_by_socket_fn=lambda **kwargs: (),
        tmux_cleanup_history_store_cls=lambda paths: type('Store', (), {'append': staticmethod(lambda event: None)})(),
    )

    assert seen['priority_pids'] == (111,)
    assert seen['pid_metadata'][111]['job_id'] == 'job-object-legacy'
    assert seen['pid_metadata'][111]['job_owner_pid'] == 111
    assert seen['pid_metadata'][222]['job_id'] == 'job-object-legacy'
    assert seen['pid_metadata'][222]['job_owner_pid'] == 111


__all__ = []
