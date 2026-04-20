from __future__ import annotations

from dataclasses import dataclass

from ccbd.models import LeaseHealth

from .models import CcbdServiceError, DaemonHandle


@dataclass
class DaemonStartState:
    keeper_started: bool
    started: bool = False
    incompatible_restart_requested: bool = False
    unreachable_restart_requested: bool = False
    direct_spawn_requested: bool = False


def poll_daemon_start_iteration(
    context,
    *,
    state: DaemonStartState,
    ensure_keeper_started_fn,
    inspect_daemon_fn,
    connect_compatible_daemon_fn,
    should_restart_unreachable_daemon_fn,
    restart_unreachable_daemon_fn,
    spawn_ccbd_process_fn,
) -> DaemonHandle | None:
    _manager, _guard, inspection = inspect_daemon_fn(context)
    handle = maybe_connect_daemon(
        context,
        inspection,
        state=state,
        connect_compatible_daemon_fn=connect_compatible_daemon_fn,
    )
    if handle is not None:
        return handle
    if maybe_restart_unreachable_daemon(
        context,
        inspection,
        state=state,
        should_restart_unreachable_daemon_fn=should_restart_unreachable_daemon_fn,
        restart_unreachable_daemon_fn=restart_unreachable_daemon_fn,
    ):
        return None
    maybe_request_spawn(
        context,
        inspection,
        state=state,
        ensure_keeper_started_fn=ensure_keeper_started_fn,
        spawn_ccbd_process_fn=spawn_ccbd_process_fn,
    )
    return None


def maybe_connect_daemon(
    context,
    inspection,
    *,
    state: DaemonStartState,
    connect_compatible_daemon_fn,
) -> DaemonHandle | None:
    if not inspection.socket_connectable:
        return None
    handle = connect_compatible_daemon_fn(
        context,
        inspection,
        restart_on_mismatch=not state.incompatible_restart_requested,
    )
    if handle is not None:
        return DaemonHandle(client=handle.client, inspection=inspection, started=state.started)
    if not state.incompatible_restart_requested:
        state.started = True
        state.incompatible_restart_requested = True
    return None


def maybe_restart_unreachable_daemon(
    context,
    inspection,
    *,
    state: DaemonStartState,
    should_restart_unreachable_daemon_fn,
    restart_unreachable_daemon_fn,
) -> bool:
    if state.unreachable_restart_requested:
        return False
    if not should_restart_unreachable_daemon_fn(inspection):
        return False
    restart_unreachable_daemon_fn(context, inspection)
    state.started = True
    state.unreachable_restart_requested = True
    return True


def maybe_request_spawn(
    context,
    inspection,
    *,
    state: DaemonStartState,
    ensure_keeper_started_fn,
    spawn_ccbd_process_fn,
) -> None:
    if inspection.health not in {LeaseHealth.MISSING, LeaseHealth.UNMOUNTED, LeaseHealth.STALE}:
        return
    state.started = True
    if state.keeper_started or state.direct_spawn_requested:
        return
    spawn_ccbd_process_fn(context)
    state.keeper_started = bool(ensure_keeper_started_fn(context))
    state.direct_spawn_requested = True


def finalize_daemon_start(
    context,
    *,
    started: bool,
    inspect_daemon_fn,
    connect_compatible_daemon_fn,
    incompatible_daemon_error_fn,
) -> DaemonHandle:
    _manager, _guard, inspection = inspect_daemon_fn(context)
    handle = connect_compatible_daemon_fn(context, inspection, restart_on_mismatch=False)
    if handle is not None:
        return DaemonHandle(client=handle.client, inspection=inspection, started=started)
    if inspection.socket_connectable:
        raise CcbdServiceError(incompatible_daemon_error_fn())
    raise CcbdServiceError(f'ccbd is unavailable: {inspection.reason}')


__all__ = [
    'DaemonStartState',
    'finalize_daemon_start',
    'poll_daemon_start_iteration',
]
