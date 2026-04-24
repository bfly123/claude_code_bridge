from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from agents.config_identity import project_config_identity_payload
from agents.config_loader import load_project_config
from ccbd.keeper import KeeperState, KeeperStateStore
from ccbd.models import CcbdLease, LeaseHealth, LeaseInspection, MountState
from ccbd.services.lifecycle import CcbdLifecycleStore, build_lifecycle
from ccbd.services.mount import MountManager
from ccbd.socket_client import CcbdClientError
from cli.context import CliContext
from cli.models import ParsedStartCommand
import cli.services.daemon as daemon_service
from project.resolver import bootstrap_project
from storage.paths import PathLayout
import pytest


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _context(project_root: Path, config_text: str) -> CliContext:
    project_root.mkdir(parents=True, exist_ok=True)
    _write(project_root / '.ccb' / 'ccb.config', config_text)
    project = bootstrap_project(project_root)
    command = ParsedStartCommand(project=None, agent_names=(), restore=False, auto_permission=False)
    return CliContext(command=command, cwd=project_root, project=project, paths=PathLayout(project_root))


def _inspection(
    context: CliContext,
    *,
    health: LeaseHealth,
    socket_connectable: bool,
    pid_alive: bool,
    heartbeat_fresh: bool,
    mount_state: MountState = MountState.MOUNTED,
    reason: str,
) -> LeaseInspection:
    lease = CcbdLease(
        project_id=context.project.project_id,
        ccbd_pid=12345,
        socket_path=str(context.paths.ccbd_socket_path),
        owner_uid=1000,
        boot_id='boot-id',
        started_at='2026-03-29T00:00:00Z',
        last_heartbeat_at='2026-03-29T00:00:00Z',
        mount_state=mount_state,
        generation=1,
    )
    return LeaseInspection(
        lease=lease,
        health=health,
        pid_alive=pid_alive,
        socket_connectable=socket_connectable,
        heartbeat_fresh=heartbeat_fresh,
        takeover_allowed=health in {LeaseHealth.MISSING, LeaseHealth.UNMOUNTED, LeaseHealth.STALE},
        reason=reason,
    )


def _repeat_last_inspection(inspections):
    items = tuple(inspections)
    assert items
    iterator = iter(items)
    last = items[-1]

    def _inspect(context):
        del context
        try:
            current = next(iterator)
        except StopIteration:
            current = last
        return None, None, current

    return _inspect


def test_daemon_matches_project_config_uses_signature_not_only_agent_names(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-signature'
    ctx = _context(project_root, 'agent1:codex\n')
    old_signature = project_config_identity_payload(load_project_config(project_root).config)['config_signature']

    _write(project_root / '.ccb' / 'ccb.config', 'agent1:claude\n')
    ctx = _context(project_root, 'agent1:claude\n')

    class FakeClient:
        def ping(self, target: str = 'ccbd') -> dict:
            assert target == 'ccbd'
            return {
                'known_agents': ['agent1'],
                'config_signature': old_signature,
            }

    assert daemon_service._daemon_matches_project_config(ctx, FakeClient()) is False


def test_ensure_daemon_started_restarts_healthy_daemon_on_config_drift(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-drift'
    ctx = _context(project_root, 'agent1:codex,agent2:codex,agent3:claude\n')
    expected = project_config_identity_payload(load_project_config(project_root).config)

    inspections = iter(
        [
            _inspection(
                ctx,
                health=LeaseHealth.HEALTHY,
                socket_connectable=True,
                pid_alive=True,
                heartbeat_fresh=True,
                reason='healthy',
            ),
            _inspection(
                ctx,
                health=LeaseHealth.UNMOUNTED,
                socket_connectable=False,
                pid_alive=False,
                heartbeat_fresh=False,
                mount_state=MountState.UNMOUNTED,
                reason='lease_unmounted',
            ),
            _inspection(
                ctx,
                health=LeaseHealth.UNMOUNTED,
                socket_connectable=False,
                pid_alive=False,
                heartbeat_fresh=False,
                mount_state=MountState.UNMOUNTED,
                reason='lease_unmounted',
            ),
            _inspection(
                ctx,
                health=LeaseHealth.HEALTHY,
                socket_connectable=True,
                pid_alive=True,
                heartbeat_fresh=True,
                reason='healthy',
            ),
        ]
    )

    shutdown_calls: list[str] = []
    keeper_calls: list[Path] = []
    running_intents: list[str] = []
    probe_payloads = iter(
        [
            {
                'known_agents': ['codex', 'claude', 'gemini'],
                'config_signature': 'old-signature',
            },
            {
                'known_agents': list(expected['known_agents']),
                'config_signature': expected['config_signature'],
            },
        ]
    )
    current_payload = {
        'known_agents': ['codex', 'claude', 'gemini'],
        'config_signature': 'old-signature',
    }

    class FakeClient:
        def __init__(self, socket_path, *, timeout_s=None) -> None:
            del socket_path
            if timeout_s == daemon_service.CONTROL_PLANE_RPC_TIMEOUT_S:
                current_payload.update(next(probe_payloads))
            self._payload = dict(current_payload)

        def ping(self, target: str = 'ccbd') -> dict:
            assert target == 'ccbd'
            return dict(self._payload)

        def stop_all(self, *, force: bool = False) -> dict:
            assert force is False
            shutdown_calls.append(str(self._payload.get('config_signature') or ''))
            return {'ok': True}

    monkeypatch.setattr(daemon_service, 'inspect_daemon', _repeat_last_inspection(inspections))
    monkeypatch.setattr(daemon_service, 'CcbdClient', FakeClient)
    monkeypatch.setattr(daemon_service, '_record_running_intent', lambda context: running_intents.append(context.project.project_id))
    monkeypatch.setattr(daemon_service, '_ensure_keeper_started', lambda context: keeper_calls.append(context.project.project_root) or False)

    handle = daemon_service.ensure_daemon_started(ctx)

    assert handle.started is True
    assert shutdown_calls == ['old-signature']
    assert running_intents == [ctx.project.project_id]
    assert keeper_calls


def test_connect_compatible_daemon_does_not_shutdown_on_transient_ping_timeout(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / 'repo-transient-ping-timeout'
    ctx = _context(project_root, 'agent1:codex\n')
    inspection = _inspection(
        ctx,
        health=LeaseHealth.HEALTHY,
        socket_connectable=True,
        pid_alive=True,
        heartbeat_fresh=True,
        reason='healthy',
    )
    shutdown_calls: list[str] = []
    captured: list[float | None] = []

    class FakeClient:
        def __init__(self, socket_path, *, timeout_s=None) -> None:
            del socket_path
            self.timeout_s = timeout_s
            captured.append(timeout_s)

        def ping(self, target: str = 'ccbd') -> dict:
            assert target == 'ccbd'
            raise CcbdClientError('timed out')

        def shutdown(self) -> dict:
            shutdown_calls.append('shutdown')
            return {'ok': True}

    monkeypatch.setattr(daemon_service, 'CcbdClient', FakeClient)

    handle = daemon_service._connect_compatible_daemon(
        ctx,
        inspection,
        restart_on_mismatch=True,
    )

    assert handle is not None
    assert isinstance(handle.client, FakeClient)
    assert captured == [daemon_service.CONTROL_PLANE_RPC_TIMEOUT_S, None]
    assert handle.client.timeout_s is None
    assert shutdown_calls == []


def test_ensure_daemon_started_waits_for_degraded_unreachable_daemon_with_fresh_heartbeat(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / 'repo-degraded'
    ctx = _context(project_root, 'cmd,agent1:codex; agent2:codex,agent3:claude\n')
    expected = project_config_identity_payload(load_project_config(project_root).config)

    inspections = iter(
        [
            _inspection(
                ctx,
                health=LeaseHealth.DEGRADED,
                socket_connectable=False,
                pid_alive=True,
                heartbeat_fresh=True,
                reason='socket_unreachable',
            ),
            _inspection(
                ctx,
                health=LeaseHealth.HEALTHY,
                socket_connectable=True,
                pid_alive=True,
                heartbeat_fresh=True,
                reason='healthy',
            ),
        ]
    )

    restart_calls: list[str] = []
    keeper_calls: list[Path] = []
    running_intents: list[str] = []

    class FakeClient:
        def __init__(self, socket_path, *, timeout_s=None) -> None:
            del socket_path, timeout_s

        def ping(self, target: str = 'ccbd') -> dict:
            assert target == 'ccbd'
            return {
                'known_agents': list(expected['known_agents']),
                'config_signature': expected['config_signature'],
            }

    monkeypatch.setattr(daemon_service, 'inspect_daemon', _repeat_last_inspection(inspections))
    monkeypatch.setattr(daemon_service, 'CcbdClient', FakeClient)
    monkeypatch.setattr(daemon_service, '_record_running_intent', lambda context: running_intents.append(context.project.project_id))
    monkeypatch.setattr(daemon_service, '_ensure_keeper_started', lambda context: keeper_calls.append(context.project.project_root) or False)
    monkeypatch.setattr(
        daemon_service,
        '_restart_unreachable_daemon',
        lambda context, inspection: restart_calls.append(inspection.reason),
    )

    handle = daemon_service.ensure_daemon_started(ctx)

    assert handle.started is False
    assert restart_calls == []
    assert running_intents == [ctx.project.project_id]
    assert keeper_calls == [ctx.project.project_root]


def test_ensure_daemon_started_restarts_stale_unreachable_daemon_with_live_pid(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / 'repo-stale'
    ctx = _context(project_root, 'cmd,agent1:codex; agent2:codex,agent3:claude\n')
    expected = project_config_identity_payload(load_project_config(project_root).config)

    inspections = iter(
        [
            _inspection(
                ctx,
                health=LeaseHealth.STALE,
                socket_connectable=False,
                pid_alive=True,
                heartbeat_fresh=False,
                reason='heartbeat_stale,socket_unreachable',
            ),
            _inspection(
                ctx,
                health=LeaseHealth.STALE,
                socket_connectable=False,
                pid_alive=False,
                heartbeat_fresh=False,
                reason='pid_missing,heartbeat_stale,socket_unreachable',
            ),
            _inspection(
                ctx,
                health=LeaseHealth.HEALTHY,
                socket_connectable=True,
                pid_alive=True,
                heartbeat_fresh=True,
                reason='healthy',
            ),
        ]
    )

    restart_calls: list[str] = []
    keeper_calls: list[Path] = []
    running_intents: list[str] = []

    class FakeClient:
        def __init__(self, socket_path, *, timeout_s=None) -> None:
            del socket_path, timeout_s

        def ping(self, target: str = 'ccbd') -> dict:
            assert target == 'ccbd'
            return {
                'known_agents': list(expected['known_agents']),
                'config_signature': expected['config_signature'],
            }

    monkeypatch.setattr(daemon_service, 'inspect_daemon', _repeat_last_inspection(inspections))
    monkeypatch.setattr(daemon_service, 'CcbdClient', FakeClient)
    monkeypatch.setattr(daemon_service, '_record_running_intent', lambda context: running_intents.append(context.project.project_id))
    monkeypatch.setattr(daemon_service, '_ensure_keeper_started', lambda context: keeper_calls.append(context.project.project_root) or False)
    monkeypatch.setattr(
        daemon_service,
        '_restart_unreachable_daemon',
        lambda context, inspection: restart_calls.append(inspection.reason),
    )

    handle = daemon_service.ensure_daemon_started(ctx)

    assert handle.started is True
    assert restart_calls == ['heartbeat_stale,socket_unreachable']
    assert running_intents == [ctx.project.project_id]
    assert keeper_calls


def test_restart_unreachable_daemon_does_not_unmount_replaced_lease_holder(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from cli.services.daemon_runtime import processes as daemon_processes

    project_root = tmp_path / 'repo-stale-replaced'
    ctx = _context(project_root, 'agent1:codex\n')
    inspection = _inspection(
        ctx,
        health=LeaseHealth.STALE,
        socket_connectable=False,
        pid_alive=True,
        heartbeat_fresh=False,
        reason='heartbeat_stale,socket_unreachable',
    )
    inspected_lease = replace(inspection.lease, daemon_instance_id='daemon-a')
    inspection = replace(inspection, lease=inspected_lease)
    mark_calls: list[dict[str, object]] = []
    kill_calls: list[tuple[int, bool]] = []

    def _mark_unmounted(**kwargs):
        mark_calls.append(dict(kwargs))
        raise RuntimeError('ccbd lease holder changed')

    manager = SimpleNamespace(
        mark_unmounted=_mark_unmounted,
        load_state=lambda: inspection.lease,
    )

    monkeypatch.setattr(daemon_processes, 'wait_for_daemon_release', lambda context, timeout_s, inspect_daemon_fn: True)

    daemon_processes.restart_unreachable_daemon(
        ctx,
        inspection,
        shutdown_timeout_s=1.0,
        inspect_daemon_fn=lambda context: (manager, None, inspection),
        manager_factory=lambda paths: manager,
        kill_pid_fn=lambda pid, force: kill_calls.append((pid, force)),
    )

    assert kill_calls == [(inspection.lease.ccbd_pid, False)]
    assert mark_calls == [
        {
            'expected_pid': inspection.lease.ccbd_pid,
            'expected_daemon_instance_id': 'daemon-a',
        }
    ]


def test_connect_mounted_daemon_recovers_after_transient_degraded_unreachable_daemon(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / 'repo-ask-recover'
    ctx = _context(project_root, 'cmd,agent1:codex; agent2:codex,agent3:claude\n')
    degraded = _inspection(
        ctx,
        health=LeaseHealth.DEGRADED,
        socket_connectable=False,
        pid_alive=True,
        heartbeat_fresh=True,
        reason='socket_unreachable',
    )
    healthy = _inspection(
        ctx,
        health=LeaseHealth.HEALTHY,
        socket_connectable=True,
        pid_alive=True,
        heartbeat_fresh=True,
        reason='healthy',
    )
    expected_handle = daemon_service.DaemonHandle(client=None, inspection=healthy, started=False)
    inspections = iter([degraded, healthy])

    monkeypatch.setattr(daemon_service, 'inspect_daemon', _repeat_last_inspection(inspections))
    monkeypatch.setattr(
        daemon_service,
        '_connect_compatible_daemon',
        lambda context, inspection, restart_on_mismatch: expected_handle if inspection.socket_connectable else None,
    )
    monkeypatch.setattr(
        daemon_service,
        'ensure_daemon_started',
        lambda context: (_ for _ in ()).throw(AssertionError('should not restart daemon')),
    )

    handle = daemon_service.connect_mounted_daemon(ctx, allow_restart_stale=True)

    assert handle is expected_handle


def test_connect_mounted_daemon_restarts_unmounted_daemon_when_recovery_allowed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / 'repo-unmounted-recover'
    ctx = _context(project_root, 'cmd,agent1:codex; agent2:codex,agent3:claude\n')
    inspection = _inspection(
        ctx,
        health=LeaseHealth.UNMOUNTED,
        socket_connectable=False,
        pid_alive=False,
        heartbeat_fresh=False,
        mount_state=MountState.UNMOUNTED,
        reason='lease_unmounted',
    )
    expected_handle = daemon_service.DaemonHandle(client=None, inspection=inspection, started=True)

    monkeypatch.setattr(daemon_service, 'inspect_daemon', lambda context: (None, None, inspection))
    monkeypatch.setattr(daemon_service, 'ensure_daemon_started', lambda context: expected_handle)

    handle = daemon_service.connect_mounted_daemon(ctx, allow_restart_stale=True)

    assert handle is expected_handle


def test_connect_mounted_daemon_waits_when_lifecycle_is_starting(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / 'repo-starting-recover'
    ctx = _context(project_root, 'agent1:codex\n')
    inspection = SimpleNamespace(
        phase='starting',
        desired_state='running',
        health=LeaseHealth.MISSING,
        socket_connectable=False,
        pid_alive=False,
        heartbeat_fresh=False,
        takeover_allowed=True,
        reason='lease_missing',
        lease=None,
        last_failure_reason=None,
    )
    expected_handle = daemon_service.DaemonHandle(client=None, inspection=inspection, started=True)

    monkeypatch.setattr(daemon_service, 'inspect_daemon', lambda context: (None, None, inspection))
    monkeypatch.setattr(daemon_service, 'ensure_daemon_started', lambda context: expected_handle)

    handle = daemon_service.connect_mounted_daemon(ctx, allow_restart_stale=True)

    assert handle is expected_handle


def test_connect_mounted_daemon_does_not_restart_when_lifecycle_desired_stopped(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / 'repo-stopped-no-recover'
    ctx = _context(project_root, 'agent1:codex\n')
    inspection = SimpleNamespace(
        phase='unmounted',
        desired_state='stopped',
        health=LeaseHealth.UNMOUNTED,
        socket_connectable=False,
        pid_alive=False,
        heartbeat_fresh=False,
        takeover_allowed=True,
        reason='lease_unmounted',
        lease=None,
        last_failure_reason=None,
    )

    monkeypatch.setattr(daemon_service, 'inspect_daemon', lambda context: (None, None, inspection))
    monkeypatch.setattr(
        daemon_service,
        'ensure_daemon_started',
        lambda context: (_ for _ in ()).throw(AssertionError('should not autostart while desired_state=stopped')),
    )

    with pytest.raises(daemon_service.CcbdServiceError, match='project ccbd is unmounted; run `ccb` first'):
        daemon_service.connect_mounted_daemon(ctx, allow_restart_stale=True)


def test_inspect_daemon_prefers_lifecycle_phase_over_lease_mount_state(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-lifecycle-inspection'
    ctx = _context(project_root, 'agent1:codex\n')
    lifecycle_store = CcbdLifecycleStore(ctx.paths)
    lifecycle_store.save(
        build_lifecycle(
            project_id=ctx.project.project_id,
            occurred_at='2026-04-21T00:00:00Z',
            desired_state='running',
            phase='starting',
            generation=7,
            keeper_pid=4321,
            socket_path=ctx.paths.ccbd_socket_path,
        )
    )
    manager = MountManager(ctx.paths)
    manager.mark_mounted(
        project_id=ctx.project.project_id,
        pid=1234,
        socket_path=ctx.paths.ccbd_socket_path,
        generation=3,
    )
    manager.mark_unmounted()

    _manager, _guard, inspection = daemon_service.inspect_daemon(ctx)

    assert inspection.phase == 'starting'
    assert inspection.desired_state == 'running'
    assert inspection.generation == 7
    assert inspection.health is LeaseHealth.UNMOUNTED


def test_ensure_daemon_started_surfaces_keeper_failure_reason_when_startup_stalls(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / 'repo-keeper-failure'
    ctx = _context(project_root, 'agent1:codex\n')
    inspection = _inspection(
        ctx,
        health=LeaseHealth.UNMOUNTED,
        socket_connectable=False,
        pid_alive=False,
        heartbeat_fresh=False,
        mount_state=MountState.UNMOUNTED,
        reason='lease_unmounted',
    )
    KeeperStateStore(ctx.paths).save(
        KeeperState(
            project_id=ctx.project.project_id,
            keeper_pid=12345,
            started_at='2026-04-16T00:00:00Z',
            last_check_at='2026-04-16T00:00:01Z',
            state='running',
            restart_count=1,
            last_restart_at='2026-04-16T00:00:01Z',
            last_failure_reason='layout_spec must include each configured agent exactly once and cmd',
        )
    )

    monkeypatch.setattr(daemon_service, 'inspect_daemon', lambda context: (None, None, inspection))
    monkeypatch.setattr(daemon_service, '_record_running_intent', lambda context: None)
    monkeypatch.setattr(daemon_service, '_ensure_keeper_started', lambda context: False)
    monkeypatch.setattr(daemon_service, '_DEF_START_TIMEOUT_S', 0.0)

    with pytest.raises(
        daemon_service.CcbdServiceError,
        match='keeper_last_failure: layout_spec must include each configured agent exactly once and cmd',
    ):
        daemon_service.ensure_daemon_started(ctx)
