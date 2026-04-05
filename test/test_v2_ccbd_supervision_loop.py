from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from agents.models import AgentRuntime, AgentSpec, AgentState, PermissionMode, ProjectConfig, QueuePolicy, RestoreMode, RuntimeMode, WorkspaceMode
from ccbd.services.registry import AgentRegistry
from ccbd.services.runtime import RuntimeService
from ccbd.supervision import RuntimeSupervisionLoop, SupervisionEventStore
from project.resolver import bootstrap_project
from provider_core.contracts import ProviderSessionBinding
from storage.paths import PathLayout


def _runtime(agent_name: str, *, project_id: str, layout: PathLayout, pid: int, health: str) -> AgentRuntime:
    state = AgentState.IDLE if health == 'healthy' else AgentState.DEGRADED
    return AgentRuntime(
        agent_name=agent_name,
        state=state,
        pid=pid,
        started_at='2026-03-18T00:00:00Z',
        last_seen_at='2026-03-18T00:00:00Z',
        runtime_ref=None if state is AgentState.DEGRADED else f'tmux:%{pid}',
        session_ref=None if state is AgentState.DEGRADED else f'{agent_name}-session',
        workspace_path=str(layout.workspace_path(agent_name)),
        project_id=project_id,
        backend_type='tmux',
        queue_depth=0,
        socket_path=None,
        health=health,
    )


def _provider_config(*providers: str) -> ProjectConfig:
    agents: dict[str, AgentSpec] = {}
    for provider in providers:
        agents[provider] = AgentSpec(
            name=provider,
            provider=provider,
            target='.',
            workspace_mode=WorkspaceMode.GIT_WORKTREE,
            workspace_root=None,
            runtime_mode=RuntimeMode.PANE_BACKED,
            restore_default=RestoreMode.AUTO,
            permission_default=PermissionMode.MANUAL,
            queue_policy=QueuePolicy.SERIAL_PER_AGENT,
        )
    return ProjectConfig(version=2, default_agents=tuple(providers), agents=agents)


class RecoveringBindingSession:
    def __init__(
        self,
        *,
        pane_id: str,
        fake_session_id: str,
        recovered_pane_id: str,
        recovered_session_id: str,
        recover_ok: bool = True,
    ) -> None:
        self.pane_id = pane_id
        self.terminal = 'tmux'
        self.fake_session_id = fake_session_id
        self.fake_session_path = None
        self._recovered_pane_id = recovered_pane_id
        self._recovered_session_id = recovered_session_id
        self._recover_ok = recover_ok
        self.ensure_calls = 0

    def ensure_pane(self):
        self.ensure_calls += 1
        if not self._recover_ok:
            return False, 'pane_dead'
        self.pane_id = self._recovered_pane_id
        self.fake_session_id = self._recovered_session_id
        return True, self.pane_id


def _binding_map(provider: str, session: RecoveringBindingSession) -> dict[str, ProviderSessionBinding]:
    return {
        provider: ProviderSessionBinding(
            provider=provider,
            load_session=lambda root, instance, provider=provider, session=session: (
                session if instance in {None, provider} else None
            ),
            session_id_attr='fake_session_id',
            session_path_attr='fake_session_path',
        )
    }


def test_runtime_supervision_loop_recovers_idle_degraded_agent(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-supervision-recover'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    session = RecoveringBindingSession(
        pane_id='%41',
        fake_session_id='codex-session-old',
        recovered_pane_id='%88',
        recovered_session_id='codex-session-new',
    )
    runtime_service = RuntimeService(
        layout,
        registry,
        ctx.project_id,
        session_bindings=_binding_map('codex', session),
        clock=lambda: '2026-03-18T00:00:00Z',
    )
    registry.upsert(_runtime('codex', project_id=ctx.project_id, layout=layout, pid=101, health='pane-dead'))
    loop = RuntimeSupervisionLoop(
        project_id=ctx.project_id,
        layout=layout,
        config=config,
        registry=registry,
        runtime_service=runtime_service,
        clock=lambda: '2026-03-18T00:00:10Z',
        generation_getter=lambda: 7,
    )

    statuses = loop.reconcile_once()

    assert statuses == {'codex': 'healthy'}
    runtime = registry.get('codex')
    assert runtime is not None
    assert runtime.state is AgentState.IDLE
    assert runtime.health == 'healthy'
    assert runtime.runtime_ref == 'tmux:%88'
    assert runtime.session_ref == 'codex-session-new'
    assert runtime.daemon_generation == 7
    assert runtime.desired_state == 'mounted'
    assert runtime.reconcile_state == 'steady'
    assert runtime.restart_count == 1
    assert runtime.last_reconcile_at == '2026-03-18T00:00:10Z'
    assert runtime.last_failure_reason is None
    assert session.ensure_calls == 1
    events = SupervisionEventStore(layout).read_all()
    assert [event.event_kind for event in events] == ['recover_started', 'recover_succeeded']
    assert events[0].prior_health == 'pane-dead'
    assert events[1].result_health == 'healthy'
    assert events[1].daemon_generation == 7


def test_runtime_supervision_loop_reflows_project_namespace_on_pane_recovery(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-supervision-reflow'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex', 'claude')
    registry = AgentRegistry(layout, config)
    runtime_service = RuntimeService(layout, registry, ctx.project_id, clock=lambda: '2026-03-18T00:00:00Z')
    degraded = _runtime('codex', project_id=ctx.project_id, layout=layout, pid=101, health='pane-dead')
    degraded.runtime_ref = 'tmux:%41'
    degraded.tmux_socket_path = str(layout.ccbd_tmux_socket_path)
    degraded.pane_state = 'dead'
    steady = _runtime('claude', project_id=ctx.project_id, layout=layout, pid=202, health='healthy')
    steady.runtime_ref = 'tmux:%202'
    steady.tmux_socket_path = str(layout.ccbd_tmux_socket_path)
    registry.upsert(degraded)
    registry.upsert(steady)
    remount_calls: list[str] = []

    def _remount(reason: str) -> None:
        remount_calls.append(reason)
        refreshed = registry.get('codex')
        assert refreshed is not None
        registry.upsert(
            AgentRuntime(
                **{
                    **refreshed.__dict__,
                    'state': AgentState.IDLE,
                    'health': 'healthy',
                    'runtime_ref': 'tmux:%55',
                    'session_ref': 'codex-session-reflowed',
                    'reconcile_state': 'steady',
                    'pane_state': 'alive',
                    'pane_id': '%55',
                    'active_pane_id': '%55',
                    'last_failure_reason': None,
                }
            )
        )

    def _refresh(*args, **kwargs):
        raise AssertionError('project namespace pane recovery should use namespace reflow, not local ensure_pane')

    monkeypatch.setattr(runtime_service, 'refresh_provider_binding', _refresh)
    loop = RuntimeSupervisionLoop(
        project_id=ctx.project_id,
        layout=layout,
        config=config,
        registry=registry,
        runtime_service=runtime_service,
        remount_project_fn=_remount,
        clock=lambda: '2026-03-18T00:00:10Z',
        generation_getter=lambda: 44,
    )

    statuses = loop.reconcile_once()

    assert statuses == {'codex': 'healthy', 'claude': 'healthy'}
    assert remount_calls == ['pane_recovery:codex']
    runtime = registry.get('codex')
    assert runtime is not None
    assert runtime.runtime_ref == 'tmux:%55'
    assert runtime.session_ref == 'codex-session-reflowed'
    events = SupervisionEventStore(layout).read_all()
    assert [event.event_kind for event in events] == ['recover_started', 'recover_succeeded']


def test_runtime_supervision_loop_skips_namespace_reflow_when_other_agent_busy(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-supervision-reflow-busy'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex', 'claude')
    registry = AgentRegistry(layout, config)
    session = RecoveringBindingSession(
        pane_id='%41',
        fake_session_id='codex-session-old',
        recovered_pane_id='%88',
        recovered_session_id='codex-session-new',
    )
    runtime_service = RuntimeService(
        layout,
        registry,
        ctx.project_id,
        session_bindings=_binding_map('codex', session),
        clock=lambda: '2026-03-18T00:00:00Z',
    )
    degraded = _runtime('codex', project_id=ctx.project_id, layout=layout, pid=101, health='pane-dead')
    degraded.runtime_ref = 'tmux:%41'
    degraded.tmux_socket_path = str(layout.ccbd_tmux_socket_path)
    degraded.pane_state = 'dead'
    busy = _runtime('claude', project_id=ctx.project_id, layout=layout, pid=202, health='healthy')
    busy.state = AgentState.BUSY
    busy.runtime_ref = 'tmux:%202'
    busy.tmux_socket_path = str(layout.ccbd_tmux_socket_path)
    registry.upsert(degraded)
    registry.upsert(busy)
    remount_calls: list[str] = []

    loop = RuntimeSupervisionLoop(
        project_id=ctx.project_id,
        layout=layout,
        config=config,
        registry=registry,
        runtime_service=runtime_service,
        remount_project_fn=lambda reason: remount_calls.append(reason),
        clock=lambda: '2026-03-18T00:00:10Z',
        generation_getter=lambda: 45,
    )

    statuses = loop.reconcile_once()

    assert statuses == {'codex': 'healthy', 'claude': 'healthy'}
    assert remount_calls == []
    assert session.ensure_calls == 1


def test_runtime_supervision_loop_mounts_missing_runtime(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-supervision-mount'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime_service = RuntimeService(layout, registry, ctx.project_id, clock=lambda: '2026-03-18T00:00:00Z')
    seen_starting: list[AgentState] = []

    def _mount(agent_name: str) -> None:
        current = registry.get(agent_name)
        assert current is not None
        seen_starting.append(current.state)
        registry.upsert(
            AgentRuntime(
                **{
                    **_runtime(agent_name, project_id=ctx.project_id, layout=layout, pid=101, health='healthy').__dict__,
                    'runtime_ref': 'tmux:%55',
                    'session_ref': 'codex-session-new',
                }
            )
        )

    loop = RuntimeSupervisionLoop(
        project_id=ctx.project_id,
        layout=layout,
        config=config,
        registry=registry,
        runtime_service=runtime_service,
        mount_agent_fn=_mount,
        clock=lambda: '2026-03-18T00:00:10Z',
        generation_getter=lambda: 21,
    )

    statuses = loop.reconcile_once()

    assert statuses == {'codex': 'healthy'}
    assert seen_starting == [AgentState.STARTING]
    runtime = registry.get('codex')
    assert runtime is not None
    assert runtime.state is AgentState.IDLE
    assert runtime.health == 'healthy'
    assert runtime.runtime_ref == 'tmux:%55'
    assert runtime.session_ref == 'codex-session-new'
    assert runtime.daemon_generation == 21
    assert runtime.desired_state == 'mounted'
    assert runtime.reconcile_state == 'steady'
    assert runtime.restart_count == 1
    assert runtime.last_reconcile_at == '2026-03-18T00:00:10Z'
    events = SupervisionEventStore(layout).read_all()
    assert [event.event_kind for event in events] == ['mount_started', 'mount_succeeded']
    assert events[0].prior_health == 'unmounted'
    assert events[1].result_health == 'healthy'


def test_runtime_supervision_loop_remounts_foreign_pane_binding(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-supervision-foreign'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime_service = RuntimeService(layout, registry, ctx.project_id, clock=lambda: '2026-03-18T00:00:00Z')
    registry.upsert(_runtime('codex', project_id=ctx.project_id, layout=layout, pid=101, health='pane-foreign'))
    calls: list[str] = []

    def _mount(agent_name: str) -> None:
        calls.append(agent_name)
        registry.upsert(
            AgentRuntime(
                **{
                    **_runtime(agent_name, project_id=ctx.project_id, layout=layout, pid=202, health='healthy').__dict__,
                    'runtime_ref': 'tmux:%202',
                    'session_ref': 'codex-session-remounted',
                }
            )
        )

    loop = RuntimeSupervisionLoop(
        project_id=ctx.project_id,
        layout=layout,
        config=config,
        registry=registry,
        runtime_service=runtime_service,
        mount_agent_fn=_mount,
        clock=lambda: '2026-03-18T00:00:10Z',
        generation_getter=lambda: 33,
    )

    statuses = loop.reconcile_once()

    assert statuses == {'codex': 'healthy'}
    assert calls == ['codex']
    runtime = registry.get('codex')
    assert runtime is not None
    assert runtime.runtime_ref == 'tmux:%202'
    assert runtime.session_ref == 'codex-session-remounted'
    assert runtime.reconcile_state == 'steady'
    events = SupervisionEventStore(layout).read_all()
    assert [event.event_kind for event in events] == ['mount_started', 'mount_succeeded']


def test_runtime_supervision_loop_reflows_project_namespace_on_foreign_namespace_pane(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-supervision-foreign-reflow'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = replace(_provider_config('codex', 'claude'), cmd_enabled=True, layout_spec='cmd; codex, claude')
    registry = AgentRegistry(layout, config)
    runtime_service = RuntimeService(layout, registry, ctx.project_id, clock=lambda: '2026-03-18T00:00:00Z')
    degraded = _runtime('codex', project_id=ctx.project_id, layout=layout, pid=101, health='pane-foreign')
    degraded.runtime_ref = 'tmux:%41'
    degraded.tmux_socket_path = str(layout.ccbd_tmux_socket_path)
    degraded.pane_state = 'foreign'
    steady = _runtime('claude', project_id=ctx.project_id, layout=layout, pid=202, health='healthy')
    steady.runtime_ref = 'tmux:%202'
    steady.tmux_socket_path = str(layout.ccbd_tmux_socket_path)
    registry.upsert(degraded)
    registry.upsert(steady)
    remount_calls: list[str] = []

    def _remount(reason: str) -> None:
        remount_calls.append(reason)
        refreshed = registry.get('codex')
        assert refreshed is not None
        registry.upsert(
            AgentRuntime(
                **{
                    **refreshed.__dict__,
                    'state': AgentState.IDLE,
                    'health': 'healthy',
                    'runtime_ref': 'tmux:%55',
                    'session_ref': 'codex-session-reflowed',
                    'reconcile_state': 'steady',
                    'pane_state': 'alive',
                    'pane_id': '%55',
                    'active_pane_id': '%55',
                    'last_failure_reason': None,
                }
            )
        )

    def _refresh(*args, **kwargs):
        raise AssertionError('foreign namespace pane should use namespace reflow, not local ensure_pane')

    monkeypatch.setattr(runtime_service, 'refresh_provider_binding', _refresh)
    loop = RuntimeSupervisionLoop(
        project_id=ctx.project_id,
        layout=layout,
        config=config,
        registry=registry,
        runtime_service=runtime_service,
        remount_project_fn=_remount,
        clock=lambda: '2026-03-18T00:00:10Z',
        generation_getter=lambda: 45,
    )

    statuses = loop.reconcile_once()

    assert statuses == {'codex': 'healthy', 'claude': 'healthy'}
    assert remount_calls == ['pane_recovery:codex']
    runtime = registry.get('codex')
    assert runtime is not None
    assert runtime.runtime_ref == 'tmux:%55'
    assert runtime.session_ref == 'codex-session-reflowed'
    events = SupervisionEventStore(layout).read_all()
    assert [event.event_kind for event in events] == ['recover_started', 'recover_succeeded']


def test_runtime_supervision_loop_skips_healthy_runtime(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-supervision-healthy'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime_service = RuntimeService(layout, registry, ctx.project_id, clock=lambda: '2026-03-18T00:00:00Z')
    registry.upsert(_runtime('codex', project_id=ctx.project_id, layout=layout, pid=101, health='healthy'))
    loop = RuntimeSupervisionLoop(
        project_id=ctx.project_id,
        layout=layout,
        config=config,
        registry=registry,
        runtime_service=runtime_service,
        clock=lambda: '2026-03-18T00:00:10Z',
        generation_getter=lambda: 9,
    )
    calls: list[str] = []

    def _refresh(agent_name: str, *, recover: bool = False):
        calls.append(f'{agent_name}:{recover}')
        raise AssertionError('healthy runtime should not trigger background refresh')

    monkeypatch.setattr(runtime_service, 'refresh_provider_binding', _refresh)

    statuses = loop.reconcile_once()

    assert statuses == {'codex': 'healthy'}
    assert calls == []
    runtime = registry.get('codex')
    assert runtime is not None
    assert runtime.daemon_generation == 9
    assert runtime.desired_state == 'mounted'
    assert runtime.reconcile_state == 'steady'
    assert SupervisionEventStore(layout).read_all() == []


def test_runtime_supervision_loop_skips_session_missing_runtime(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-supervision-session-missing'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime_service = RuntimeService(layout, registry, ctx.project_id, clock=lambda: '2026-03-18T00:00:00Z')
    registry.upsert(_runtime('codex', project_id=ctx.project_id, layout=layout, pid=101, health='session-missing'))
    loop = RuntimeSupervisionLoop(
        project_id=ctx.project_id,
        layout=layout,
        config=config,
        registry=registry,
        runtime_service=runtime_service,
        clock=lambda: '2026-03-18T00:00:10Z',
        generation_getter=lambda: 11,
    )
    calls: list[str] = []

    def _refresh(agent_name: str, *, recover: bool = False):
        calls.append(f'{agent_name}:{recover}')
        raise AssertionError('session-missing runtime should not thrash on heartbeat')

    monkeypatch.setattr(runtime_service, 'refresh_provider_binding', _refresh)

    statuses = loop.reconcile_once()

    assert statuses == {'codex': 'session-missing'}
    assert calls == []
    runtime = registry.get('codex')
    assert runtime is not None
    assert runtime.daemon_generation == 11
    assert runtime.reconcile_state == 'degraded'
    assert SupervisionEventStore(layout).read_all() == []


def test_runtime_supervision_loop_persists_failure_reason_and_event(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-supervision-failure'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    session = RecoveringBindingSession(
        pane_id='%41',
        fake_session_id='codex-session-old',
        recovered_pane_id='%88',
        recovered_session_id='codex-session-new',
        recover_ok=False,
    )
    runtime_service = RuntimeService(
        layout,
        registry,
        ctx.project_id,
        session_bindings=_binding_map('codex', session),
        clock=lambda: '2026-03-18T00:00:00Z',
    )
    registry.upsert(_runtime('codex', project_id=ctx.project_id, layout=layout, pid=101, health='pane-dead'))
    loop = RuntimeSupervisionLoop(
        project_id=ctx.project_id,
        layout=layout,
        config=config,
        registry=registry,
        runtime_service=runtime_service,
        clock=lambda: '2026-03-18T00:00:10Z',
        generation_getter=lambda: 12,
    )

    statuses = loop.reconcile_once()

    assert statuses == {'codex': 'pane-dead'}
    runtime = registry.get('codex')
    assert runtime is not None
    assert runtime.state is AgentState.DEGRADED
    assert runtime.daemon_generation == 12
    assert runtime.reconcile_state == 'degraded'
    assert runtime.restart_count == 1
    assert runtime.last_reconcile_at == '2026-03-18T00:00:10Z'
    assert runtime.last_failure_reason == 'pane-dead'
    events = SupervisionEventStore(layout).read_all()
    assert [event.event_kind for event in events] == ['recover_started', 'recover_failed']
    assert events[1].details == {'reason': 'pane-dead'}


def test_runtime_supervision_loop_persists_mount_failure(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-supervision-mount-failure'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime_service = RuntimeService(layout, registry, ctx.project_id, clock=lambda: '2026-03-18T00:00:00Z')

    def _mount(agent_name: str) -> None:
        del agent_name
        raise RuntimeError('launch boom')

    loop = RuntimeSupervisionLoop(
        project_id=ctx.project_id,
        layout=layout,
        config=config,
        registry=registry,
        runtime_service=runtime_service,
        mount_agent_fn=_mount,
        clock=lambda: '2026-03-18T00:00:10Z',
        generation_getter=lambda: 22,
    )

    statuses = loop.reconcile_once()

    assert statuses == {'codex': 'start-failed'}
    runtime = registry.get('codex')
    assert runtime is not None
    assert runtime.state is AgentState.FAILED
    assert runtime.health == 'start-failed'
    assert runtime.daemon_generation == 22
    assert runtime.desired_state == 'mounted'
    assert runtime.reconcile_state == 'failed'
    assert runtime.restart_count == 1
    assert runtime.last_reconcile_at == '2026-03-18T00:00:10Z'
    assert runtime.last_failure_reason == 'RuntimeError: launch boom'
    events = SupervisionEventStore(layout).read_all()
    assert [event.event_kind for event in events] == ['mount_started', 'mount_failed']
    assert events[1].details == {'reason': 'RuntimeError: launch boom'}


def test_runtime_supervision_loop_applies_failure_backoff(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-supervision-backoff'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime_service = RuntimeService(layout, registry, ctx.project_id, clock=lambda: '2026-03-18T00:00:00Z')
    runtime = _runtime('codex', project_id=ctx.project_id, layout=layout, pid=101, health='pane-dead')
    runtime.restart_count = 2
    runtime.last_reconcile_at = '2026-03-18T00:00:09Z'
    runtime.last_failure_reason = 'pane-dead'
    registry.upsert(runtime)
    loop = RuntimeSupervisionLoop(
        project_id=ctx.project_id,
        layout=layout,
        config=config,
        registry=registry,
        runtime_service=runtime_service,
        clock=lambda: '2026-03-18T00:00:10Z',
        generation_getter=lambda: 13,
    )
    calls: list[str] = []

    def _refresh(agent_name: str, *, recover: bool = False):
        calls.append(f'{agent_name}:{recover}')
        raise AssertionError('runtime in backoff should not trigger recovery')

    monkeypatch.setattr(runtime_service, 'refresh_provider_binding', _refresh)

    statuses = loop.reconcile_once()

    assert statuses == {'codex': 'pane-dead'}
    assert calls == []
    persisted = registry.get('codex')
    assert persisted is not None
    assert persisted.daemon_generation == 13
    assert persisted.reconcile_state == 'degraded'
    assert persisted.restart_count == 2
    assert persisted.last_reconcile_at == '2026-03-18T00:00:09Z'
    assert SupervisionEventStore(layout).read_all() == []


def test_runtime_supervision_loop_applies_mount_failure_backoff(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-supervision-mount-backoff'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime_service = RuntimeService(layout, registry, ctx.project_id, clock=lambda: '2026-03-18T00:00:00Z')
    registry.upsert(
        AgentRuntime(
            **{
                **_runtime('codex', project_id=ctx.project_id, layout=layout, pid=101, health='pane-dead').__dict__,
                'state': AgentState.FAILED,
                'health': 'start-failed',
                'restart_count': 2,
                'last_reconcile_at': '2026-03-18T00:00:09Z',
                'last_failure_reason': 'RuntimeError: launch boom',
            }
        )
    )
    calls: list[str] = []

    def _mount(agent_name: str) -> None:
        calls.append(agent_name)
        raise AssertionError('failed runtime in backoff should not trigger mount')

    loop = RuntimeSupervisionLoop(
        project_id=ctx.project_id,
        layout=layout,
        config=config,
        registry=registry,
        runtime_service=runtime_service,
        mount_agent_fn=_mount,
        clock=lambda: '2026-03-18T00:00:10Z',
        generation_getter=lambda: 23,
    )

    statuses = loop.reconcile_once()

    assert statuses == {'codex': 'start-failed'}
    assert calls == []
    persisted = registry.get('codex')
    assert persisted is not None
    assert persisted.daemon_generation == 23
    assert persisted.reconcile_state == 'failed'
    assert persisted.restart_count == 2
    assert persisted.last_reconcile_at == '2026-03-18T00:00:09Z'
    assert SupervisionEventStore(layout).read_all() == []
