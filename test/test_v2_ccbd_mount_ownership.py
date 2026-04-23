from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from ccbd.api_models import DeliveryScope, MessageEnvelope
from ccbd.app import CcbdApp
from ccbd.models import LeaseHealth, MountState
from ccbd.services.health import HealthMonitor
from ccbd.services.mount import MountManager
from ccbd.services.ownership import OwnershipConflictError, OwnershipGuard
from ccbd.services.project_namespace_state import ProjectNamespaceState, ProjectNamespaceStateStore
from ccbd.services.runtime import RuntimeService
from agents.models import (
    AgentRuntime,
    AgentSpec,
    AgentState,
    PermissionMode,
    ProjectConfig,
    QueuePolicy,
    RestoreMode,
    RuntimeBindingSource,
    RuntimeMode,
    WorkspaceMode,
)
from ccbd.services.registry import AgentRegistry
from project.resolver import bootstrap_project
from storage.paths import PathLayout


class FakeTmuxBackend:
    def __init__(
        self,
        *,
        exists: bool = True,
        alive: bool = True,
        pane_title: str = 'CCB-codex-demo',
        owner_agent: str | None = 'codex',
        owner_project_id: str | None = 'proj-1',
    ) -> None:
        self.exists = exists
        self.alive = alive
        self.pane_title = pane_title
        self.owner_agent = owner_agent
        self.owner_project_id = owner_project_id

    def pane_exists(self, pane_id: str) -> bool:
        return self.exists

    def is_tmux_pane_alive(self, pane_id: str) -> bool:
        return self.exists and self.alive

    def describe_pane(self, pane_id: str, *, user_options: tuple[str, ...] = ()) -> dict[str, str]:
        described = {
            'pane_id': pane_id,
            'pane_title': self.pane_title,
            'pane_dead': '0' if (self.exists and self.alive) else '1',
        }
        for name in user_options:
            if name == '@ccb_agent':
                described[name] = str(self.owner_agent or '')
            elif name == '@ccb_project_id':
                described[name] = str(self.owner_project_id or '')
            else:
                described[name] = ''
        return described


class FakeTmuxSession:
    def __init__(
        self,
        *,
        pane_id: str,
        backend: FakeTmuxBackend,
        recovered_pane_id: str | None = None,
        ensure_ok: bool = False,
        session_path: str = '/tmp/fake-session.json',
    ) -> None:
        self.terminal = 'tmux'
        self._pane_id = pane_id
        self._backend = backend
        self._recovered_pane_id = recovered_pane_id
        self._ensure_ok = ensure_ok
        self.fake_session_path = session_path
        self.session_file = Path(session_path)
        self.data = {
            'agent_name': 'codex',
            'ccb_project_id': 'proj-1',
            'pane_id': pane_id,
            'terminal': 'tmux',
        }

    @property
    def pane_id(self) -> str:
        return self._pane_id

    def backend(self):
        return self._backend

    def ensure_pane(self) -> tuple[bool, str]:
        if not self._ensure_ok:
            return False, 'pane unavailable'
        if self._recovered_pane_id:
            self._pane_id = self._recovered_pane_id
        self._backend.exists = True
        self._backend.alive = True
        return True, self._pane_id


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


class Clock:
    def __init__(self, values: list[str]) -> None:
        self._values = list(values)
        self._index = 0

    def __call__(self) -> str:
        if self._index >= len(self._values):
            return self._values[-1]
        value = self._values[self._index]
        self._index += 1
        return value


def _runtime(agent_name: str, *, project_id: str, layout: PathLayout, pid: int) -> AgentRuntime:
    return AgentRuntime(
        agent_name=agent_name,
        state=AgentState.IDLE,
        pid=pid,
        started_at='2026-03-18T00:00:00Z',
        last_seen_at='2026-03-18T00:00:00Z',
        runtime_ref=f'{agent_name}-runtime',
        session_ref=f'{agent_name}-session',
        workspace_path=str(layout.workspace_path(agent_name)),
        project_id=project_id,
        backend_type='tmux',
        queue_depth=0,
        socket_path=None,
        health='healthy',
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


def test_mount_manager_roundtrip_and_unmount(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    clock = Clock(
        [
            '2026-03-18T00:00:00Z',
            '2026-03-18T00:00:05Z',
            '2026-03-18T00:00:10Z',
        ]
    )
    manager = MountManager(layout, clock=clock, uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')

    mounted = manager.mark_mounted(
        project_id=ctx.project_id,
        pid=321,
        socket_path=layout.ccbd_socket_path,
        generation=2,
    )
    assert mounted.mount_state is MountState.MOUNTED
    assert mounted.generation == 2

    refreshed = manager.refresh_heartbeat()
    assert refreshed.last_heartbeat_at == '2026-03-18T00:00:05Z'

    unmounted = manager.mark_unmounted()
    assert unmounted is not None
    assert unmounted.mount_state is MountState.UNMOUNTED
    assert manager.load_state().mount_state is MountState.UNMOUNTED


def test_mount_manager_does_not_revive_unmounted_lease_on_heartbeat(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-race'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    clock = Clock(
        [
            '2026-03-18T00:00:00Z',
            '2026-03-18T00:00:05Z',
            '2026-03-18T00:00:10Z',
        ]
    )
    manager = MountManager(layout, clock=clock, uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')

    manager.mark_mounted(
        project_id=ctx.project_id,
        pid=321,
        socket_path=layout.ccbd_socket_path,
        generation=2,
    )
    manager.mark_unmounted()
    lease = manager.refresh_heartbeat()

    assert lease.mount_state is MountState.UNMOUNTED
    assert manager.load_state().mount_state is MountState.UNMOUNTED


def test_mount_manager_refresh_heartbeat_rejects_replaced_lease_holder(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-replaced-holder'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    clock = Clock(
        [
            '2026-03-18T00:00:00Z',
            '2026-03-18T00:00:05Z',
        ]
    )
    manager = MountManager(layout, clock=clock, uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')

    manager.mark_mounted(
        project_id=ctx.project_id,
        pid=321,
        socket_path=layout.ccbd_socket_path,
        generation=2,
        daemon_instance_id='daemon-a',
    )
    manager.mark_mounted(
        project_id=ctx.project_id,
        pid=654,
        socket_path=layout.ccbd_socket_path,
        generation=3,
        daemon_instance_id='daemon-b',
    )

    with pytest.raises(RuntimeError, match='lease holder changed'):
        manager.refresh_heartbeat(expected_pid=321, expected_daemon_instance_id='daemon-a')

    lease = manager.load_state()
    assert lease is not None
    assert lease.ccbd_pid == 654
    assert lease.daemon_instance_id == 'daemon-b'


def test_mount_manager_mark_unmounted_rejects_replaced_lease_holder(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-replaced-unmount'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    manager = MountManager(layout, clock=lambda: '2026-03-18T00:00:00Z', uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')

    manager.mark_mounted(
        project_id=ctx.project_id,
        pid=321,
        socket_path=layout.ccbd_socket_path,
        generation=2,
        daemon_instance_id='daemon-a',
    )
    manager.mark_mounted(
        project_id=ctx.project_id,
        pid=654,
        socket_path=layout.ccbd_socket_path,
        generation=3,
        daemon_instance_id='daemon-b',
    )

    with pytest.raises(RuntimeError, match='lease holder changed'):
        manager.mark_unmounted(expected_pid=321, expected_daemon_instance_id='daemon-a')

    lease = manager.load_state()
    assert lease is not None
    assert lease.mount_state is MountState.MOUNTED
    assert lease.ccbd_pid == 654


def test_ownership_guard_blocks_healthy_lease_and_allows_stale_takeover(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)

    manager = MountManager(
        layout,
        clock=lambda: '2026-03-18T00:00:00Z',
        uid_getter=lambda: 1000,
        boot_id_getter=lambda: 'boot-1',
    )
    manager.mark_mounted(project_id=ctx.project_id, pid=111, socket_path=layout.ccbd_socket_path, generation=3)

    healthy_guard = OwnershipGuard(
        layout,
        manager,
        clock=lambda: '2026-03-18T00:00:05Z',
        pid_exists=lambda pid: True,
        socket_probe=lambda path: True,
        heartbeat_grace_seconds=15,
    )
    inspection = healthy_guard.inspect()
    assert inspection.health is LeaseHealth.HEALTHY
    with pytest.raises(OwnershipConflictError):
        healthy_guard.verify_or_takeover(project_id=ctx.project_id, pid=222, socket_path=layout.ccbd_socket_path)

    stale_guard = OwnershipGuard(
        layout,
        manager,
        clock=lambda: '2026-03-18T00:01:00Z',
        pid_exists=lambda pid: False,
        socket_probe=lambda path: False,
        heartbeat_grace_seconds=15,
    )
    inspection = stale_guard.inspect()
    assert inspection.health is LeaseHealth.STALE
    assert stale_guard.verify_or_takeover(project_id=ctx.project_id, pid=222, socket_path=layout.ccbd_socket_path) == 4


def test_ownership_guard_marks_fresh_socket_failure_as_degraded(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-degraded'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    manager = MountManager(
        layout,
        clock=lambda: '2026-03-18T00:00:00Z',
        uid_getter=lambda: 1000,
        boot_id_getter=lambda: 'boot-1',
    )
    manager.mark_mounted(project_id=ctx.project_id, pid=111, socket_path=layout.ccbd_socket_path, generation=5)

    degraded_guard = OwnershipGuard(
        layout,
        manager,
        clock=lambda: '2026-03-18T00:00:05Z',
        pid_exists=lambda pid: True,
        socket_probe=lambda path: False,
        heartbeat_grace_seconds=15,
    )
    inspection = degraded_guard.inspect()
    assert inspection.health is LeaseHealth.DEGRADED
    assert inspection.takeover_allowed is False
    assert inspection.reason == 'socket_unreachable'
    with pytest.raises(OwnershipConflictError):
        degraded_guard.verify_or_takeover(project_id=ctx.project_id, pid=222, socket_path=layout.ccbd_socket_path)


def test_ownership_guard_allows_takeover_when_socket_and_heartbeat_are_stale(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-stale-matrix'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    manager = MountManager(
        layout,
        clock=lambda: '2026-03-18T00:00:00Z',
        uid_getter=lambda: 1000,
        boot_id_getter=lambda: 'boot-1',
    )
    manager.mark_mounted(project_id=ctx.project_id, pid=111, socket_path=layout.ccbd_socket_path, generation=7)

    stale_guard = OwnershipGuard(
        layout,
        manager,
        clock=lambda: '2026-03-18T00:01:00Z',
        pid_exists=lambda pid: True,
        socket_probe=lambda path: False,
        heartbeat_grace_seconds=15,
    )
    inspection = stale_guard.inspect()
    assert inspection.health is LeaseHealth.STALE
    assert inspection.takeover_allowed is True
    assert inspection.reason == 'heartbeat_stale,socket_unreachable'
    assert stale_guard.verify_or_takeover(project_id=ctx.project_id, pid=222, socket_path=layout.ccbd_socket_path) == 8


def test_health_monitor_marks_orphaned_runtime(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    registry.upsert(_runtime('codex', project_id=ctx.project_id, layout=layout, pid=99999))
    original = registry.get('codex')
    manager = MountManager(layout, clock=lambda: '2026-03-18T00:00:00Z', uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')
    guard = OwnershipGuard(layout, manager, clock=lambda: '2026-03-18T00:00:00Z', pid_exists=lambda pid: False, socket_probe=lambda path: False)
    runtime_service = RuntimeService(layout, registry, ctx.project_id, clock=lambda: '2026-03-18T00:00:10Z')
    monitor = HealthMonitor(
        registry,
        guard,
        runtime_service=runtime_service,
        clock=lambda: '2026-03-18T00:00:10Z',
        pid_exists=lambda pid: False,
    )

    assert monitor.collect_orphans() == ('codex',)
    runtime = registry.get('codex')
    assert runtime is not None
    assert runtime.state is AgentState.DEGRADED
    assert runtime.health == 'orphaned'
    assert original is not None
    assert runtime.binding_generation == original.binding_generation
    assert runtime.runtime_generation == original.runtime_generation


def test_health_monitor_marks_dead_tmux_pane_degraded_without_rebinding(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime = _runtime('codex', project_id=ctx.project_id, layout=layout, pid=1234)
    runtime = AgentRuntime(
        **{
            **runtime.__dict__,
            'runtime_ref': 'tmux:%dead',
            'session_ref': '/tmp/old-session.json',
        }
    )
    registry.upsert(runtime)
    manager = MountManager(layout, clock=lambda: '2026-03-18T00:00:00Z', uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')
    guard = OwnershipGuard(layout, manager, clock=lambda: '2026-03-18T00:00:00Z', pid_exists=lambda pid: True, socket_probe=lambda path: True)
    backend = FakeTmuxBackend(exists=True, alive=False)
    session = FakeTmuxSession(
        pane_id='%dead',
        backend=backend,
        ensure_ok=True,
        recovered_pane_id='%live',
        session_path='/tmp/new-session.json',
    )
    monitor = HealthMonitor(
        registry,
        guard,
        clock=lambda: '2026-03-18T00:00:10Z',
        pid_exists=lambda pid: True,
        session_bindings={
            'codex': type(
                'Binding',
                (),
                {
                    'load_session': staticmethod(lambda work_dir, instance=None: session),
                    'session_path_attr': 'fake_session_path',
                    'session_id_attr': 'fake_session_id',
                },
            )()
        },
    )

    assert monitor.check_all()['codex'] == 'pane-dead'
    refreshed = registry.get('codex')
    assert refreshed is not None
    assert refreshed.state is AgentState.DEGRADED
    assert refreshed.health == 'pane-dead'
    assert refreshed.runtime_ref == 'tmux:%dead'
    assert refreshed.session_ref == '/tmp/new-session.json'
    assert refreshed.pane_id == '%dead'
    assert refreshed.active_pane_id == '%dead'
    assert refreshed.pane_state == 'dead'


def test_health_monitor_prefers_dead_pane_signal_before_pid_orphaning(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-pane-before-pid'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime = _runtime('codex', project_id=ctx.project_id, layout=layout, pid=1234)
    runtime = AgentRuntime(
        **{
            **runtime.__dict__,
            'runtime_ref': 'tmux:%dead',
            'session_ref': '/tmp/old-session.json',
        }
    )
    registry.upsert(runtime)
    manager = MountManager(layout, clock=lambda: '2026-03-18T00:00:00Z', uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')
    guard = OwnershipGuard(layout, manager, clock=lambda: '2026-03-18T00:00:00Z', pid_exists=lambda pid: False, socket_probe=lambda path: True)
    backend = FakeTmuxBackend(exists=True, alive=False)
    session = FakeTmuxSession(
        pane_id='%dead',
        backend=backend,
        ensure_ok=True,
        recovered_pane_id='%live',
        session_path='/tmp/new-session.json',
    )
    monitor = HealthMonitor(
        registry,
        guard,
        clock=lambda: '2026-03-18T00:00:10Z',
        pid_exists=lambda pid: False,
        session_bindings={
            'codex': type(
                'Binding',
                (),
                {
                    'load_session': staticmethod(lambda work_dir, instance=None: session),
                    'session_path_attr': 'fake_session_path',
                    'session_id_attr': 'fake_session_id',
                },
            )()
        },
    )

    assert monitor.check_all()['codex'] == 'pane-dead'
    refreshed = registry.get('codex')
    assert refreshed is not None
    assert refreshed.state is AgentState.DEGRADED
    assert refreshed.health == 'pane-dead'
    assert refreshed.runtime_ref == 'tmux:%dead'
    assert refreshed.session_ref == '/tmp/new-session.json'
    assert refreshed.pane_id == '%dead'
    assert refreshed.active_pane_id == '%dead'
    assert refreshed.pane_state == 'dead'


def test_health_monitor_preserves_last_binding_when_tmux_pane_missing_and_unrecoverable(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime = _runtime('codex', project_id=ctx.project_id, layout=layout, pid=1234)
    runtime = AgentRuntime(
        **{
            **runtime.__dict__,
            'runtime_ref': 'tmux:%dead',
            'session_ref': '/tmp/old-session.json',
        }
    )
    registry.upsert(runtime)
    manager = MountManager(layout, clock=lambda: '2026-03-18T00:00:00Z', uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')
    guard = OwnershipGuard(layout, manager, clock=lambda: '2026-03-18T00:00:00Z', pid_exists=lambda pid: True, socket_probe=lambda path: True)
    backend = FakeTmuxBackend(exists=False, alive=False)
    session = FakeTmuxSession(
        pane_id='%dead',
        backend=backend,
        ensure_ok=False,
    )
    monitor = HealthMonitor(
        registry,
        guard,
        clock=lambda: '2026-03-18T00:00:10Z',
        pid_exists=lambda pid: True,
        session_bindings={
            'codex': type(
                'Binding',
                (),
                {
                    'load_session': staticmethod(lambda work_dir, instance=None: session),
                    'session_path_attr': 'fake_session_path',
                    'session_id_attr': 'fake_session_id',
                },
            )()
        },
    )

    assert monitor.check_all()['codex'] == 'pane-missing'
    degraded = registry.get('codex')
    assert degraded is not None
    assert degraded.state is AgentState.DEGRADED
    assert degraded.health == 'pane-missing'
    assert degraded.runtime_ref == 'tmux:%dead'
    assert degraded.session_ref == '/tmp/fake-session.json'
    assert degraded.pane_id == '%dead'
    assert degraded.active_pane_id == '%dead'
    assert degraded.pane_state == 'missing'


def test_health_monitor_marks_live_foreign_tmux_pane_degraded(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-foreign-pane'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime = _runtime('codex', project_id=ctx.project_id, layout=layout, pid=1234)
    runtime = AgentRuntime(
        **{
            **runtime.__dict__,
            'runtime_ref': 'tmux:%foreign',
            'session_ref': '/tmp/old-session.json',
        }
    )
    registry.upsert(runtime)
    manager = MountManager(layout, clock=lambda: '2026-03-18T00:00:00Z', uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')
    guard = OwnershipGuard(layout, manager, clock=lambda: '2026-03-18T00:00:00Z', pid_exists=lambda pid: True, socket_probe=lambda path: True)
    backend = FakeTmuxBackend(exists=True, alive=True, owner_agent='demo', owner_project_id='foreign-project')
    session = FakeTmuxSession(
        pane_id='%foreign',
        backend=backend,
        ensure_ok=False,
    )
    monitor = HealthMonitor(
        registry,
        guard,
        clock=lambda: '2026-03-18T00:00:10Z',
        pid_exists=lambda pid: True,
        session_bindings={
            'codex': type(
                'Binding',
                (),
                {
                    'load_session': staticmethod(lambda work_dir, instance=None: session),
                    'session_path_attr': 'fake_session_path',
                    'session_id_attr': 'fake_session_id',
                },
            )()
        },
    )

    assert monitor.check_all()['codex'] == 'pane-foreign'
    degraded = registry.get('codex')
    assert degraded is not None
    assert degraded.state is AgentState.DEGRADED
    assert degraded.health == 'pane-foreign'
    assert degraded.pane_state == 'foreign'
    assert degraded.active_pane_id is None


def test_health_monitor_marks_same_socket_detached_namespace_pane_foreign(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-namespace-detached-pane'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime = _runtime('codex', project_id=ctx.project_id, layout=layout, pid=1234)
    runtime = AgentRuntime(
        **{
            **runtime.__dict__,
            'runtime_ref': 'tmux:%foreign',
            'session_ref': '/tmp/old-session.json',
            'tmux_socket_path': str(layout.ccbd_tmux_socket_path),
        }
    )
    registry.upsert(runtime)
    manager = MountManager(layout, clock=lambda: '2026-03-18T00:00:00Z', uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')
    guard = OwnershipGuard(layout, manager, clock=lambda: '2026-03-18T00:00:00Z', pid_exists=lambda pid: True, socket_probe=lambda path: True)

    class NamespaceBackend(FakeTmuxBackend):
        def __init__(self) -> None:
            super().__init__(exists=True, alive=True, owner_agent='codex', owner_project_id='proj-1')
            self._socket_path = str(layout.ccbd_tmux_socket_path)

        def _tmux_run(self, args, capture=False, timeout=None, check=False):
            del capture, timeout, check
            if args[:3] == ['display-message', '-p', '-t']:
                return type(
                    'Result',
                    (),
                    {
                        'returncode': 0,
                        'stdout': f"{args[3]}\tdetached-codex\t0\tagent\tcodex\t{ctx.project_id}\tccbd\n",
                    },
                )()
            raise AssertionError(args)

    session = FakeTmuxSession(
        pane_id='%foreign',
        backend=NamespaceBackend(),
        ensure_ok=False,
    )
    ProjectNamespaceStateStore(layout).save(
        ProjectNamespaceState(
            project_id=ctx.project_id,
            namespace_epoch=3,
            tmux_socket_path=str(layout.ccbd_tmux_socket_path),
            tmux_session_name='ccb-repo',
        )
    )
    monitor = HealthMonitor(
        registry,
        guard,
        clock=lambda: '2026-03-18T00:00:10Z',
        pid_exists=lambda pid: True,
        session_bindings={
            'codex': type(
                'Binding',
                (),
                {
                    'load_session': staticmethod(lambda work_dir, instance=None: session),
                    'session_path_attr': 'fake_session_path',
                    'session_id_attr': 'fake_session_id',
                },
            )()
        },
        namespace_state_store=ProjectNamespaceStateStore(layout),
    )

    assert monitor.check_all()['codex'] == 'pane-foreign'
    degraded = registry.get('codex')
    assert degraded is not None
    assert degraded.health == 'pane-foreign'
    assert degraded.pane_state == 'foreign'
    assert degraded.active_pane_id is None


def test_health_monitor_preserves_session_id_evidence_without_rebinding_runtime(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-session-id'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime = _runtime('codex', project_id=ctx.project_id, layout=layout, pid=1234)
    runtime = AgentRuntime(
        **{
            **runtime.__dict__,
            'runtime_ref': 'tmux:%dead',
            'session_ref': None,
        }
    )
    registry.upsert(runtime)
    manager = MountManager(layout, clock=lambda: '2026-03-18T00:00:00Z', uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')
    guard = OwnershipGuard(layout, manager, clock=lambda: '2026-03-18T00:00:00Z', pid_exists=lambda pid: True, socket_probe=lambda path: True)
    backend = FakeTmuxBackend(exists=True, alive=False)
    session = FakeTmuxSession(
        pane_id='%dead',
        backend=backend,
        ensure_ok=True,
        recovered_pane_id='%live',
        session_path=str(tmp_path / 'agent1-session.json'),
    )
    session.fake_session_id = 'session-id-123'
    monitor = HealthMonitor(
        registry,
        guard,
        clock=lambda: '2026-03-18T00:00:10Z',
        pid_exists=lambda pid: True,
        session_bindings={
            'codex': type(
                'Binding',
                (),
                {
                    'load_session': staticmethod(lambda work_dir, instance=None: session),
                    'session_path_attr': 'fake_session_path',
                    'session_id_attr': 'fake_session_id',
                },
            )()
        },
    )

    assert monitor.check_all()['codex'] == 'pane-dead'
    refreshed = registry.get('codex')
    assert refreshed is not None
    assert refreshed.runtime_ref == 'tmux:%dead'
    assert refreshed.session_ref == 'session-id-123'


def test_health_monitor_external_attach_skips_provider_session_lookup_and_uses_runtime_ref(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-external-runtime'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime = replace(
        _runtime('codex', project_id=ctx.project_id, layout=layout, pid=1234),
        runtime_ref='tmux:%44',
        session_ref='session:external',
        binding_source=RuntimeBindingSource.EXTERNAL_ATTACH,
    )
    registry.upsert(runtime)
    manager = MountManager(layout, clock=lambda: '2026-03-18T00:00:00Z', uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')
    guard = OwnershipGuard(layout, manager, clock=lambda: '2026-03-18T00:00:00Z', pid_exists=lambda pid: True, socket_probe=lambda path: True)
    monitor = HealthMonitor(
        registry,
        guard,
        clock=lambda: '2026-03-18T00:00:10Z',
        pid_exists=lambda pid: True,
        session_bindings={},
    )

    assert monitor.check_all()['codex'] == 'healthy'
    refreshed = registry.get('codex')
    assert refreshed is not None
    assert refreshed.health == 'healthy'
    assert refreshed.runtime_ref == 'tmux:%44'
    assert refreshed.session_ref == 'session:external'


def test_health_monitor_external_attach_preserves_external_degraded_state(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-external-state'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime = replace(
        _runtime('codex', project_id=ctx.project_id, layout=layout, pid=1234),
        runtime_ref='tmux:%77',
        session_ref='session:external',
        state=AgentState.DEGRADED,
        health='pane-dead',
        binding_source=RuntimeBindingSource.EXTERNAL_ATTACH,
    )
    registry.upsert(runtime)
    manager = MountManager(layout, clock=lambda: '2026-03-18T00:00:00Z', uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')
    guard = OwnershipGuard(layout, manager, clock=lambda: '2026-03-18T00:00:00Z', pid_exists=lambda pid: True, socket_probe=lambda path: True)
    monitor = HealthMonitor(
        registry,
        guard,
        clock=lambda: '2026-03-18T00:00:10Z',
        pid_exists=lambda pid: True,
        session_bindings={},
    )

    assert monitor.check_all()['codex'] == 'pane-dead'
    degraded = registry.get('codex')
    assert degraded is not None
    assert degraded.state is AgentState.DEGRADED
    assert degraded.health == 'pane-dead'
    assert degraded.runtime_ref == 'tmux:%77'
    assert degraded.session_ref == 'session:external'


def test_health_monitor_preserves_degraded_health_without_rebinding_evidence(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-degraded-preserve'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime = replace(
        _runtime('codex', project_id=ctx.project_id, layout=layout, pid=1234),
        state=AgentState.DEGRADED,
        pid=None,
        health='pane-dead',
        runtime_ref=None,
        session_ref=None,
    )
    registry.upsert(runtime)
    manager = MountManager(layout, clock=lambda: '2026-03-18T00:00:00Z', uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')
    guard = OwnershipGuard(layout, manager, clock=lambda: '2026-03-18T00:00:00Z', pid_exists=lambda pid: True, socket_probe=lambda path: True)
    monitor = HealthMonitor(
        registry,
        guard,
        clock=lambda: '2026-03-18T00:00:10Z',
        pid_exists=lambda pid: True,
        session_bindings={
            'codex': type(
                'Binding',
                (),
                {
                    'load_session': staticmethod(lambda work_dir, instance=None: None),
                    'session_path_attr': 'fake_session_path',
                    'session_id_attr': 'fake_session_id',
                },
            )()
        },
    )

    assert monitor.check_all()['codex'] == 'pane-dead'
    degraded = registry.get('codex')
    assert degraded is not None
    assert degraded.state is AgentState.DEGRADED
    assert degraded.health == 'pane-dead'


def test_health_monitor_rebind_uses_session_file_when_provider_session_ref_missing(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-session-file'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime = _runtime('codex', project_id=ctx.project_id, layout=layout, pid=1234)
    runtime = AgentRuntime(
        **{
            **runtime.__dict__,
            'runtime_ref': 'tmux:%dead',
            'session_ref': None,
        }
    )
    registry.upsert(runtime)
    manager = MountManager(layout, clock=lambda: '2026-03-18T00:00:00Z', uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')
    guard = OwnershipGuard(layout, manager, clock=lambda: '2026-03-18T00:00:00Z', pid_exists=lambda pid: True, socket_probe=lambda path: True)
    backend = FakeTmuxBackend(exists=True, alive=False)
    session = FakeTmuxSession(
        pane_id='%dead',
        backend=backend,
        ensure_ok=True,
        recovered_pane_id='%live',
        session_path=str(tmp_path / 'agent1-session.json'),
    )
    session.fake_session_path = ''
    monitor = HealthMonitor(
        registry,
        guard,
        clock=lambda: '2026-03-18T00:00:10Z',
        pid_exists=lambda pid: True,
        session_bindings={
            'codex': type(
                'Binding',
                (),
                {
                    'load_session': staticmethod(lambda work_dir, instance=None: session),
                    'session_path_attr': 'fake_session_path',
                    'session_id_attr': 'fake_session_id',
                },
            )()
        },
    )

    assert monitor.check_all()['codex'] == 'pane-dead'
    refreshed = registry.get('codex')
    assert refreshed is not None
    assert refreshed.state is AgentState.DEGRADED
    assert refreshed.health == 'pane-dead'
    assert refreshed.session_ref == str(tmp_path / 'agent1-session.json')


def test_health_monitor_rebind_updates_provider_session_runtime_without_duplicate_overrides(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-provider-rebind'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    runtime = AgentRuntime(
        **{
            **_runtime('codex', project_id=ctx.project_id, layout=layout, pid=1234).__dict__,
            'runtime_ref': 'tmux:%dead',
            'session_ref': '/tmp/old-session.json',
            'pane_id': '%dead',
            'active_pane_id': '%dead',
            'pane_state': 'dead',
        }
    )
    registry.upsert(runtime)
    manager = MountManager(layout, clock=lambda: '2026-03-18T00:00:00Z', uid_getter=lambda: 1000, boot_id_getter=lambda: 'boot-1')
    guard = OwnershipGuard(layout, manager, clock=lambda: '2026-03-18T00:00:00Z', pid_exists=lambda pid: True, socket_probe=lambda path: True)
    backend = FakeTmuxBackend(exists=True, alive=True)
    session = FakeTmuxSession(
        pane_id='%41',
        backend=backend,
        ensure_ok=True,
        session_path=str(tmp_path / 'codex-session.json'),
    )
    monitor = HealthMonitor(
        registry,
        guard,
        clock=lambda: '2026-03-18T00:00:10Z',
        pid_exists=lambda pid: True,
        session_bindings={
            'codex': type(
                'Binding',
                (),
                {
                    'load_session': staticmethod(lambda work_dir, instance=None: session),
                    'session_path_attr': 'fake_session_path',
                    'session_id_attr': 'fake_session_id',
                },
            )()
        },
    )

    assert monitor.check_all()['codex'] == 'healthy'
    refreshed = registry.get('codex')
    assert refreshed is not None
    assert refreshed.state is AgentState.IDLE
    assert refreshed.health == 'healthy'
    assert refreshed.runtime_ref == 'tmux:%41'
    assert refreshed.session_ref == '/tmp/old-session.json'
    assert refreshed.pane_id == '%41'
    assert refreshed.active_pane_id == '%41'
    assert refreshed.pane_state == 'alive'


def test_ccbd_heartbeat_recovers_degraded_agent_and_drains_queue(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-heartbeat-recovery'
    project_root.mkdir()
    config_path = project_root / '.ccb' / 'ccb.config'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('codex:codex\n', encoding='utf-8')
    ctx = bootstrap_project(project_root)
    app = CcbdApp(project_root)
    degraded = replace(
        _runtime('codex', project_id=ctx.project_id, layout=app.paths, pid=1234),
        state=AgentState.DEGRADED,
        pid=None,
        health='pane-dead',
        runtime_ref=None,
        session_ref=None,
    )
    app.registry.upsert(degraded)
    session = RecoveringBindingSession(
        pane_id='%41',
        fake_session_id='codex-session-old',
        recovered_pane_id='%77',
        recovered_session_id='codex-session-new',
    )
    binding = type(
        'Binding',
        (),
        {
            'load_session': staticmethod(lambda work_dir, instance=None: session if instance in {None, 'codex'} else None),
            'session_path_attr': 'fake_session_path',
            'session_id_attr': 'fake_session_id',
        },
    )()
    app.runtime_service._session_bindings = {'codex': binding}
    app.health_monitor._session_bindings = {'codex': binding}
    app.dispatcher._execution_service = None
    monkeypatch.setattr(app.mount_manager, 'refresh_heartbeat', lambda **kwargs: None)

    submit = app.dispatcher.submit(
        MessageEnvelope(
            project_id=ctx.project_id,
            to_agent='codex',
            from_actor='user',
            body='hello heartbeat',
            task_id='task-heartbeat-recovery',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit.jobs[0].job_id
    assert app.dispatcher.tick() == ()

    app.heartbeat()

    running = app.dispatcher.get(job_id)
    assert running is not None
    assert running.status.value == 'running'
    runtime = app.registry.get('codex')
    assert runtime is not None
    assert runtime.state is AgentState.BUSY
    assert runtime.health == 'healthy'
    assert runtime.runtime_ref == 'tmux:%77'
    assert runtime.session_ref == 'codex-session-new'
    assert session.ensure_calls == 1


def test_ccbd_heartbeat_starts_missing_agent_and_drains_queue(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-heartbeat-mount'
    project_root.mkdir()
    config_path = project_root / '.ccb' / 'ccb.config'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('codex:codex\n', encoding='utf-8')
    ctx = bootstrap_project(project_root)
    app = CcbdApp(project_root)
    app.dispatcher._execution_service = None
    monkeypatch.setattr(app.mount_manager, 'refresh_heartbeat', lambda **kwargs: None)
    seen: list[tuple[tuple[str, ...], bool, bool, bool, bool]] = []
    app.registry.upsert(_runtime('codex', project_id=ctx.project_id, layout=app.paths, pid=1234))

    def _start(
        *,
        agent_names: tuple[str, ...],
        restore: bool,
        auto_permission: bool,
        cleanup_tmux_orphans: bool = True,
        interactive_tmux_layout: bool = True,
    ):
        seen.append((agent_names, restore, auto_permission, cleanup_tmux_orphans, interactive_tmux_layout))
        app.registry.upsert_authority(
            replace(
                _runtime('codex', project_id=ctx.project_id, layout=app.paths, pid=1234),
                pid=None,
                runtime_ref='tmux:%9',
                session_ref='codex-mounted-session',
            )
        )
        return None

    monkeypatch.setattr(app.runtime_supervisor, 'start', _start)

    submit = app.dispatcher.submit(
        MessageEnvelope(
            project_id=ctx.project_id,
            to_agent='codex',
            from_actor='user',
            body='hello mount',
            task_id='task-heartbeat-mount',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit.jobs[0].job_id
    app.paths.agent_runtime_path('codex').unlink()
    app.registry._cache.pop('codex', None)
    assert app.dispatcher.tick() == ()

    app.heartbeat()

    assert seen == [(('codex',), False, False, False, False)]
    running = app.dispatcher.get(job_id)
    assert running is not None
    assert running.status.value == 'running'
    runtime = app.registry.get('codex')
    assert runtime is not None
    assert runtime.state is AgentState.BUSY
    assert runtime.health == 'healthy'
    assert runtime.runtime_ref == 'tmux:%9'
    assert runtime.session_ref == 'codex-mounted-session'
    assert runtime.desired_state == 'mounted'


def test_ccbd_heartbeat_uses_persisted_start_policy_for_recovery_mount(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-heartbeat-mount-policy'
    project_root.mkdir()
    config_path = project_root / '.ccb' / 'ccb.config'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('codex:codex\n', encoding='utf-8')
    ctx = bootstrap_project(project_root)
    app = CcbdApp(project_root)
    app.persist_start_policy(auto_permission=True)
    app.dispatcher._execution_service = None
    monkeypatch.setattr(app.mount_manager, 'refresh_heartbeat', lambda **kwargs: None)
    seen: list[tuple[tuple[str, ...], bool, bool, bool, bool]] = []
    app.registry.upsert(_runtime('codex', project_id=ctx.project_id, layout=app.paths, pid=1234))

    def _start(
        *,
        agent_names: tuple[str, ...],
        restore: bool,
        auto_permission: bool,
        cleanup_tmux_orphans: bool = True,
        interactive_tmux_layout: bool = True,
    ):
        seen.append((agent_names, restore, auto_permission, cleanup_tmux_orphans, interactive_tmux_layout))
        app.registry.upsert_authority(
            replace(
                _runtime('codex', project_id=ctx.project_id, layout=app.paths, pid=1234),
                pid=None,
                runtime_ref='tmux:%19',
                session_ref='codex-mounted-session',
            )
        )
        return None

    monkeypatch.setattr(app.runtime_supervisor, 'start', _start)

    submit = app.dispatcher.submit(
        MessageEnvelope(
            project_id=ctx.project_id,
            to_agent='codex',
            from_actor='user',
            body='hello mount policy',
            task_id='task-heartbeat-mount-policy',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit.jobs[0].job_id
    app.paths.agent_runtime_path('codex').unlink()
    app.registry._cache.pop('codex', None)
    assert app.dispatcher.tick() == ()

    app.heartbeat()

    assert seen == [(('codex',), True, True, False, False)]
    running = app.dispatcher.get(job_id)
    assert running is not None
    assert running.status.value == 'running'


def test_ccbd_heartbeat_keeps_backend_mounted_on_background_supervision_failure(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-heartbeat-step-failure'
    project_root.mkdir()
    config_path = project_root / '.ccb' / 'ccb.config'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('codex:codex\n', encoding='utf-8')
    ctx = bootstrap_project(project_root)
    app = CcbdApp(project_root)

    app.start()

    monkeypatch.setattr(app.health_monitor, 'check_all', lambda: {})
    monkeypatch.setattr(app.runtime_supervision, 'reconcile_once', lambda: (_ for _ in ()).throw(RuntimeError('tmux boom')))
    monkeypatch.setattr(app.dispatcher, 'reconcile_runtime_views', lambda: None)
    monkeypatch.setattr(app.dispatcher, 'tick', lambda: ())
    monkeypatch.setattr(app.dispatcher, 'poll_completions', lambda: ())
    monkeypatch.setattr(app.job_heartbeat, 'tick', lambda dispatcher: ())

    app.heartbeat()

    inspection = app.ownership_guard.inspect()
    assert inspection.health is LeaseHealth.HEALTHY
    lifecycle = app.lifecycle_store.load()
    assert lifecycle is not None
    assert lifecycle.phase == 'mounted'
    assert lifecycle.last_failure_reason == 'heartbeat:runtime_supervision: RuntimeError: tmux boom'

    app.request_shutdown()
    lease = app.mount_manager.load_state()
    assert lease is not None
    assert lease.mount_state is MountState.UNMOUNTED


def test_ccbd_request_shutdown_does_not_unmount_replaced_lease_holder(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-request-shutdown-replaced'
    project_root.mkdir()
    config_path = project_root / '.ccb' / 'ccb.config'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('codex:codex\n', encoding='utf-8')
    ctx = bootstrap_project(project_root)
    app = CcbdApp(project_root)

    app.mount_manager.mark_mounted(
        project_id=ctx.project_id,
        pid=app.pid,
        socket_path=app.paths.ccbd_socket_path,
        generation=1,
        daemon_instance_id=app.daemon_instance_id,
    )
    app.mount_manager.mark_mounted(
        project_id=ctx.project_id,
        pid=app.pid + 1,
        socket_path=app.paths.ccbd_socket_path,
        generation=2,
        daemon_instance_id='replacement-daemon',
    )

    app.request_shutdown()

    lease = app.mount_manager.load_state()
    assert lease is not None
    assert lease.mount_state is MountState.MOUNTED
    assert lease.ccbd_pid == app.pid + 1
    assert lease.daemon_instance_id == 'replacement-daemon'


def test_ccbd_foreign_pane_reflow_uses_persisted_start_policy(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-reflow-policy'
    project_root.mkdir()
    config_path = project_root / '.ccb' / 'ccb.config'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('codex:codex, claude:claude\n', encoding='utf-8')
    ctx = bootstrap_project(project_root)
    app = CcbdApp(project_root)
    app.persist_start_policy(auto_permission=True)
    seen: list[tuple[tuple[str, ...], bool, bool, bool, bool, bool, bool, str | None]] = []

    degraded = replace(
        _runtime('codex', project_id=ctx.project_id, layout=app.paths, pid=1234),
        state=AgentState.DEGRADED,
        health='pane-foreign',
        runtime_ref='tmux:%41',
        tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
        pane_state='foreign',
    )
    steady = replace(
        _runtime('claude', project_id=ctx.project_id, layout=app.paths, pid=2234),
        runtime_ref='tmux:%42',
        tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
        pane_state='alive',
    )
    app.registry.upsert(degraded)
    app.registry.upsert(steady)

    def _start(
        *,
        agent_names: tuple[str, ...],
        restore: bool,
        auto_permission: bool,
        cleanup_tmux_orphans: bool = True,
        interactive_tmux_layout: bool = True,
        recreate_namespace: bool = False,
        reflow_workspace: bool = False,
        recreate_reason: str | None = None,
    ):
        seen.append(
            (
                agent_names,
                restore,
                auto_permission,
                cleanup_tmux_orphans,
                interactive_tmux_layout,
                recreate_namespace,
                reflow_workspace,
                recreate_reason,
            )
        )
        refreshed = app.registry.get('codex')
        assert refreshed is not None
        app.registry.upsert_authority(
            replace(
                refreshed,
                state=AgentState.IDLE,
                health='healthy',
                runtime_ref='tmux:%55',
                pane_id='%55',
                active_pane_id='%55',
                pane_state='alive',
            )
        )
        return None

    monkeypatch.setattr(app.runtime_supervisor, 'start', _start)

    statuses = app.runtime_supervision.reconcile_once()

    assert statuses == {'codex': 'healthy', 'claude': 'healthy'}
    assert seen == [(
        ('codex', 'claude'),
        True,
        True,
        False,
        True,
        False,
        True,
        'pane_recovery:codex',
    )]
