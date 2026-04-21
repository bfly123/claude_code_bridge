from __future__ import annotations

from pathlib import Path

from agents.config_identity import project_config_identity_payload
from agents.config_loader import load_project_config
from ccbd.models import LeaseHealth
from ccbd.socket_client import CcbdClient, CcbdClientError

from .records import KeeperState
from .state import compute_project_id, restart_backoff_active
from .support import reap_child_processes, try_acquire_keeper_lock


def run_forever(app, *, poll_interval: float = 0.5, start_timeout_s: float = 5.0) -> int:
    lock_path = app.paths.ccbd_dir / 'keeper.lock'
    lock_handle = try_acquire_keeper_lock(lock_path)
    if lock_handle is None:
        return 0
    cleanup_transient = False
    state = initial_keeper_state(app)
    app._state_store.save(state)
    try:
        while True:
            reap_child_processes()
            state, should_stop, cleanup_transient = run_iteration(
                app,
                state=state,
                start_timeout_s=start_timeout_s,
                cleanup_transient=cleanup_transient,
            )
            app._state_store.save(state)
            if should_stop:
                return 0
            app._sleep(max(0.05, float(poll_interval)))
    finally:
        try:
            lock_handle.close()
        except Exception:
            pass
        if cleanup_transient:
            cleanup_transient_keeper_files(app, lock_path=lock_path)


def reconcile_once(app, *, state: KeeperState, start_timeout_s: float) -> KeeperState:
    now = app.clock()
    if restart_backoff_active(state=state, now=now):
        return state
    inspection = app._ownership_guard.inspect()
    connectable_state = reconcile_connectable_daemon(app, state=state, inspection=inspection, now=now)
    if connectable_state is not None:
        return connectable_state
    restart_state = restart_state_from_inspection(app, state=state, inspection=inspection, occurred_at=now)
    if restart_state is not None:
        return app._spawn_daemon(state=restart_state, start_timeout_s=start_timeout_s)
    return state


def initial_keeper_state(app) -> KeeperState:
    now = app.clock()
    return KeeperState(
        project_id=compute_project_id(app.project_root),
        keeper_pid=app.pid,
        started_at=now,
        last_check_at=now,
        state='running',
    )


def run_iteration(
    app,
    *,
    state: KeeperState,
    start_timeout_s: float,
    cleanup_transient: bool,
) -> tuple[KeeperState, bool, bool]:
    now = app.clock()
    if app._project_definition_missing():
        return state, True, True
    if shutdown_requested(app, project_id=state.project_id):
        return state.with_state('stopped', occurred_at=now), True, cleanup_transient
    checked = state.with_check(now)
    next_state = app._reconcile_once(state=checked, start_timeout_s=start_timeout_s)
    return next_state, False, cleanup_transient


def shutdown_requested(app, *, project_id: str) -> bool:
    current_intent = app._intent_store.load()
    return current_intent is not None and current_intent.project_id == project_id


def reconcile_connectable_daemon(app, *, state: KeeperState, inspection, now: str) -> KeeperState | None:
    if not inspection.socket_connectable:
        return None
    try:
        if daemon_matches_project_config(app):
            return state.with_success(occurred_at=now)
        request_shutdown(app)
        return state.with_restart_attempt(occurred_at=now)
    except Exception as exc:
        return state.with_failure(occurred_at=now, reason=f'config_check_failed:{exc}')


def restart_state_from_inspection(app, *, state: KeeperState, inspection, occurred_at: str) -> KeeperState | None:
    stale = stale_restart_state(app, state=state, inspection=inspection, occurred_at=occurred_at)
    if stale is not None:
        return stale
    if inspection.health in {LeaseHealth.MISSING, LeaseHealth.UNMOUNTED, LeaseHealth.STALE}:
        return state.with_restart_attempt(occurred_at=occurred_at)
    return None


def stale_restart_state(app, *, state: KeeperState, inspection, occurred_at: str) -> KeeperState | None:
    if inspection.health is not LeaseHealth.STALE or not inspection.pid_alive or inspection.lease is None:
        return None
    pid = int(inspection.lease.ccbd_pid or 0)
    if pid > 0:
        app._terminate_pid_tree(pid, timeout_s=1.0)
    return state.with_restart_attempt(occurred_at=occurred_at)


def daemon_matches_project_config(app) -> bool:
    expected = project_config_identity_payload(load_project_config(app.project_root).config)
    payload = CcbdClient(app.paths.ccbd_socket_path, timeout_s=0.2).ping('ccbd')
    actual_signature = str(payload.get('config_signature') or '').strip()
    if actual_signature:
        return actual_signature == expected['config_signature']
    known_agents = payload.get('known_agents')
    if not isinstance(known_agents, list):
        return False
    actual_agents = tuple(str(item).strip().lower() for item in known_agents if str(item).strip())
    return actual_agents == tuple(expected['known_agents'])


def request_shutdown(app) -> None:
    client = CcbdClient(app.paths.ccbd_socket_path, timeout_s=0.2)
    try:
        client.stop_all(force=False)
    except CcbdClientError:
        inspection = app._ownership_guard.inspect()
        if inspection.lease is not None and inspection.pid_alive:
            app._terminate_pid_tree(int(inspection.lease.ccbd_pid or 0), timeout_s=1.0)


def cleanup_transient_keeper_files(app, *, lock_path: Path) -> None:
    for path in (
        app.paths.ccbd_keeper_path,
        app.paths.ccbd_dir / 'keeper.stdout.log',
        app.paths.ccbd_dir / 'keeper.stderr.log',
        Path(lock_path),
    ):
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except Exception:
            continue
    for path in (app.paths.ccbd_dir, app.paths.ccb_dir):
        try:
            path.rmdir()
        except OSError:
            continue


__all__ = ['cleanup_transient_keeper_files', 'daemon_matches_project_config', 'reconcile_once', 'request_shutdown', 'run_forever']
