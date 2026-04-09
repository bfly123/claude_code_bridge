from __future__ import annotations

from pathlib import Path

from agents.config_identity import project_config_identity_payload
from agents.config_loader import load_project_config
from ccbd.models import CcbdLease, LeaseHealth, LeaseInspection, MountState
from ccbd.socket_client import CcbdClientError
from cli.context import CliContext
from cli.models import ParsedStartCommand
import cli.services.daemon as daemon_service
from project.resolver import bootstrap_project
from storage.paths import PathLayout


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
    spawn_calls: list[Path] = []
    client_payloads = iter(
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

    class FakeClient:
        def __init__(self, socket_path, *, timeout_s=None) -> None:
            del socket_path, timeout_s
            self._payload = next(client_payloads)

        def ping(self, target: str = 'ccbd') -> dict:
            assert target == 'ccbd'
            return dict(self._payload)

        def shutdown(self) -> dict:
            shutdown_calls.append(str(self._payload.get('config_signature') or ''))
            return {'ok': True}

    monkeypatch.setattr(daemon_service, 'inspect_daemon', lambda context: (None, None, next(inspections)))
    monkeypatch.setattr(daemon_service, 'CcbdClient', FakeClient)
    monkeypatch.setattr(daemon_service, '_ensure_keeper_started', lambda context: False)
    monkeypatch.setattr(daemon_service, '_spawn_ccbd_process', lambda context: spawn_calls.append(context.project.project_root))

    handle = daemon_service.ensure_daemon_started(ctx)

    assert handle.started is True
    assert shutdown_calls == ['old-signature']
    assert spawn_calls == [ctx.project.project_root]


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

    class FakeClient:
        def __init__(self, socket_path, *, timeout_s=None) -> None:
            del socket_path, timeout_s

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
    spawn_calls: list[Path] = []

    class FakeClient:
        def __init__(self, socket_path, *, timeout_s=None) -> None:
            del socket_path, timeout_s

        def ping(self, target: str = 'ccbd') -> dict:
            assert target == 'ccbd'
            return {
                'known_agents': list(expected['known_agents']),
                'config_signature': expected['config_signature'],
            }

    monkeypatch.setattr(daemon_service, 'inspect_daemon', lambda context: (None, None, next(inspections)))
    monkeypatch.setattr(daemon_service, 'CcbdClient', FakeClient)
    monkeypatch.setattr(daemon_service, '_ensure_keeper_started', lambda context: False)
    monkeypatch.setattr(
        daemon_service,
        '_restart_unreachable_daemon',
        lambda context, inspection: restart_calls.append(inspection.reason),
    )
    monkeypatch.setattr(daemon_service, '_spawn_ccbd_process', lambda context: spawn_calls.append(context.project.project_root))

    handle = daemon_service.ensure_daemon_started(ctx)

    assert handle.started is False
    assert restart_calls == []
    assert spawn_calls == []


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
    spawn_calls: list[Path] = []

    class FakeClient:
        def __init__(self, socket_path, *, timeout_s=None) -> None:
            del socket_path, timeout_s

        def ping(self, target: str = 'ccbd') -> dict:
            assert target == 'ccbd'
            return {
                'known_agents': list(expected['known_agents']),
                'config_signature': expected['config_signature'],
            }

    monkeypatch.setattr(daemon_service, 'inspect_daemon', lambda context: (None, None, next(inspections)))
    monkeypatch.setattr(daemon_service, 'CcbdClient', FakeClient)
    monkeypatch.setattr(daemon_service, '_ensure_keeper_started', lambda context: False)
    monkeypatch.setattr(
        daemon_service,
        '_restart_unreachable_daemon',
        lambda context, inspection: restart_calls.append(inspection.reason),
    )
    monkeypatch.setattr(daemon_service, '_spawn_ccbd_process', lambda context: spawn_calls.append(context.project.project_root))

    handle = daemon_service.ensure_daemon_started(ctx)

    assert handle.started is True
    assert restart_calls == ['heartbeat_stale,socket_unreachable']
    assert spawn_calls == [ctx.project.project_root]


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

    monkeypatch.setattr(daemon_service, 'inspect_daemon', lambda context: (None, None, next(inspections)))
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
