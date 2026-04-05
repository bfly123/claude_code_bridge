from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from agents.config_identity import project_config_identity_payload
from agents.config_loader import load_project_config
from ccbd.keeper import KeeperState, KeeperStateStore, ProjectKeeper, ShutdownIntent, ShutdownIntentStore
from ccbd.models import CcbdLease, LeaseHealth, LeaseInspection, MountState
from cli.context import CliContext
from cli.models import ParsedStartCommand
import cli.services.daemon as daemon_service
import ccbd.keeper as keeper_module
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
    lease = None
    if health is not LeaseHealth.MISSING:
        lease = CcbdLease(
            project_id=context.project.project_id,
            ccbd_pid=321,
            socket_path=str(context.paths.ccbd_socket_path),
            owner_uid=1000,
            boot_id='boot-id',
            started_at='2026-04-02T00:00:00Z',
            last_heartbeat_at='2026-04-02T00:00:00Z',
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


def test_keeper_state_store_roundtrip(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-state'
    _write(project_root / '.ccb' / 'ccb.config', 'agent1:codex\n')
    layout = PathLayout(project_root)
    state = KeeperState(
        project_id='project-1',
        keeper_pid=555,
        started_at='2026-04-02T00:00:00Z',
        last_check_at='2026-04-02T00:00:00Z',
        state='running',
        restart_count=2,
        last_restart_at='2026-04-02T00:00:10Z',
        last_failure_reason='socket_unreachable',
    )

    KeeperStateStore(layout).save(state)
    loaded = KeeperStateStore(layout).load()

    assert loaded == state


def test_project_keeper_spawns_missing_daemon(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-missing'
    ctx = _context(project_root, 'agent1:codex\n')
    spawn_calls: list[dict] = []
    keeper = ProjectKeeper(
        project_root,
        pid=777,
        spawn_ccbd_process_fn=lambda **kwargs: spawn_calls.append(dict(kwargs)),
    )
    keeper._ownership_guard = SimpleNamespace(
        inspect=lambda: _inspection(
            ctx,
            health=LeaseHealth.MISSING,
            socket_connectable=False,
            pid_alive=False,
            heartbeat_fresh=False,
            reason='lease_missing',
        )
    )
    state = KeeperState(
        project_id=ctx.project.project_id,
        keeper_pid=777,
        started_at='2026-04-02T00:00:00Z',
        last_check_at='2026-04-02T00:00:00Z',
        state='running',
    )

    next_state = keeper._reconcile_once(state=state, start_timeout_s=0.1)

    assert len(spawn_calls) == 1
    assert spawn_calls[0]['project_root'] == project_root
    assert spawn_calls[0]['keeper_pid'] == 777
    assert next_state.restart_count == 1
    assert next_state.last_failure_reason is None


def test_project_keeper_restarts_degraded_unreachable_daemon(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-crash'
    ctx = _context(project_root, 'agent1:codex\n')
    spawn_calls: list[dict] = []
    terminated: list[int] = []
    keeper = ProjectKeeper(
        project_root,
        pid=888,
        process_exists_fn=lambda pid: pid == 321,
        spawn_ccbd_process_fn=lambda **kwargs: spawn_calls.append(dict(kwargs)),
    )
    keeper._ownership_guard = SimpleNamespace(
        inspect=lambda: _inspection(
            ctx,
            health=LeaseHealth.DEGRADED,
            socket_connectable=False,
            pid_alive=True,
            heartbeat_fresh=True,
            reason='socket_unreachable',
        )
    )
    monkeypatch.setattr(
        keeper_module,
        'terminate_pid_tree',
        lambda pid, timeout_s, is_pid_alive_fn: terminated.append(pid) or True,
    )
    state = KeeperState(
        project_id=ctx.project.project_id,
        keeper_pid=888,
        started_at='2026-04-02T00:00:00Z',
        last_check_at='2026-04-02T00:00:00Z',
        state='running',
    )

    next_state = keeper._reconcile_once(state=state, start_timeout_s=0.1)

    assert terminated == [321]
    assert len(spawn_calls) == 1
    assert next_state.restart_count == 1
    assert next_state.last_failure_reason is None


def test_project_keeper_stops_when_shutdown_intent_exists(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-stop'
    ctx = _context(project_root, 'agent1:codex\n')
    layout = PathLayout(project_root)
    ShutdownIntentStore(layout).save(
        ShutdownIntent(
            project_id=ctx.project.project_id,
            requested_at='2026-04-02T00:00:00Z',
            requested_by_pid=1,
            reason='kill',
        )
    )
    keeper = ProjectKeeper(
        project_root,
        pid=999,
        sleep_fn=lambda _seconds: (_ for _ in ()).throw(AssertionError('keeper should not sleep')),
        spawn_ccbd_process_fn=lambda **kwargs: (_ for _ in ()).throw(AssertionError('keeper should not spawn')),
    )

    code = keeper.run_forever(poll_interval=0.1, start_timeout_s=0.1)
    state = KeeperStateStore(layout).load()

    assert code == 0
    assert state is not None
    assert state.state == 'stopped'


def test_project_keeper_exits_and_cleans_keeper_residue_when_config_missing(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-missing-config'
    _context(project_root, 'agent1:codex\n')
    config_path = project_root / '.ccb' / 'ccb.config'
    config_path.unlink()

    keeper = ProjectKeeper(
        project_root,
        pid=1001,
        sleep_fn=lambda _seconds: (_ for _ in ()).throw(AssertionError('keeper should exit before sleeping')),
        spawn_ccbd_process_fn=lambda **kwargs: (_ for _ in ()).throw(AssertionError('keeper should not spawn')),
    )

    code = keeper.run_forever(poll_interval=0.1, start_timeout_s=0.1)

    assert code == 0
    assert (project_root / '.ccb' / 'ccbd' / 'keeper.json').exists() is False
    assert (project_root / '.ccb' / 'ccbd' / 'keeper.lock').exists() is False
    assert (project_root / '.ccb').exists() is False


def test_reap_child_processes_drains_exited_children() -> None:
    seen: list[tuple[int, int]] = []
    responses = iter(((321, 0), (654, 0), (0, 0)))
    original = keeper_module._reap_child_processes

    reaped = original(waitpid_fn=lambda pid, flags: seen.append((pid, flags)) or next(responses))

    assert reaped == (321, 654)
    assert seen == [(-1, keeper_module.os.WNOHANG)] * 3


def test_ensure_daemon_started_waits_for_keeper_started_backend(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-keeper-start'
    ctx = _context(project_root, 'agent1:codex\n')
    expected = project_config_identity_payload(load_project_config(project_root).config)
    inspections = iter(
        [
            _inspection(
                ctx,
                health=LeaseHealth.MISSING,
                socket_connectable=False,
                pid_alive=False,
                heartbeat_fresh=False,
                reason='lease_missing',
            ),
            _inspection(
                ctx,
                health=LeaseHealth.MISSING,
                socket_connectable=False,
                pid_alive=False,
                heartbeat_fresh=False,
                reason='lease_missing',
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
    monkeypatch.setattr(daemon_service, '_ensure_keeper_started', lambda context: True)
    monkeypatch.setattr(daemon_service, '_spawn_ccbd_process', lambda context: spawn_calls.append(context.project.project_root))

    handle = daemon_service.ensure_daemon_started(ctx)

    assert handle.started is True
    assert spawn_calls == []


def test_shutdown_daemon_records_intent_and_terminates_keeper(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-kill-keeper'
    ctx = _context(project_root, 'agent1:codex\n')
    layout = PathLayout(project_root)
    KeeperStateStore(layout).save(
        KeeperState(
            project_id=ctx.project.project_id,
            keeper_pid=654,
            started_at='2026-04-02T00:00:00Z',
            last_check_at='2026-04-02T00:00:00Z',
            state='running',
        )
    )
    lease = SimpleNamespace(
        mount_state=SimpleNamespace(value='unmounted'),
        ccbd_pid=0,
        keeper_pid=None,
    )
    manager = SimpleNamespace(
        mark_unmounted=lambda: lease,
        load_state=lambda: lease,
    )
    inspection = SimpleNamespace(
        socket_connectable=False,
        pid_alive=False,
        lease=lease,
    )
    terminated: list[int] = []

    monkeypatch.setattr(daemon_service, 'inspect_daemon', lambda context: (manager, None, inspection))
    monkeypatch.setattr(daemon_service, '_wait_for_keeper_exit', lambda context, timeout_s: False)
    monkeypatch.setattr('cli.services.daemon.is_pid_alive', lambda pid: pid == 654)
    monkeypatch.setattr(
        'cli.services.daemon.terminate_pid_tree',
        lambda pid, timeout_s, is_pid_alive_fn: terminated.append(pid) or True,
    )

    summary = daemon_service.shutdown_daemon(ctx, force=False)
    intent = ShutdownIntentStore(layout).load()

    assert summary.state == 'unmounted'
    assert terminated == [654]
    assert intent is not None
    assert intent.reason == 'kill'
