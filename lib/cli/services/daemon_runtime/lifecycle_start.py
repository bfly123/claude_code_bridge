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


def poll_daemon_start_iteration(
    context,
    *,
    state: DaemonStartState,
    ensure_keeper_started_fn,
    inspect_daemon_fn,
    connect_compatible_daemon_fn,
    should_restart_unreachable_daemon_fn,
    restart_unreachable_daemon_fn,
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
    )
    return None


def maybe_connect_daemon(
    context,
    inspection,
    *,
    state: DaemonStartState,
    connect_compatible_daemon_fn,
) -> DaemonHandle | None:
    if _phase(inspection) != 'mounted' or not inspection.socket_connectable:
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
    if _phase(inspection) not in {'mounted', 'failed'}:
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
) -> None:
    if _desired_state(inspection) != 'running':
        return
    if _phase(inspection) not in {'unmounted', 'failed'}:
        return
    if inspection.health not in {LeaseHealth.MISSING, LeaseHealth.UNMOUNTED, LeaseHealth.STALE}:
        return
    state.started = True
    if state.keeper_started:
        return
    state.keeper_started = bool(ensure_keeper_started_fn(context))


def finalize_daemon_start(
    context,
    *,
    started: bool,
    inspect_daemon_fn,
    connect_compatible_daemon_fn,
    incompatible_daemon_error_fn,
) -> DaemonHandle:
    _manager, _guard, inspection = inspect_daemon_fn(context)
    phase = _phase(inspection)
    if phase == 'mounted':
        handle = connect_compatible_daemon_fn(context, inspection, restart_on_mismatch=False)
        if handle is not None:
            return DaemonHandle(client=handle.client, inspection=inspection, started=started)
        if inspection.socket_connectable:
            raise CcbdServiceError(incompatible_daemon_error_fn())
    if phase == 'starting':
        raise CcbdServiceError('ccbd is unavailable: lifecycle_starting')
    if phase == 'stopping':
        raise CcbdServiceError('ccbd is unavailable: lifecycle_stopping')
    failure_reason = str(getattr(inspection, 'last_failure_reason', '') or '').strip()
    if phase == 'failed' and failure_reason:
        raise CcbdServiceError(f'ccbd is unavailable: {inspection.reason}; lifecycle_failure: {failure_reason}')
    raise CcbdServiceError(f'ccbd is unavailable: {inspection.reason}')


def _phase(inspection) -> str:
    phase = str(getattr(inspection, 'phase', '') or '').strip()
    if phase:
        return phase
    health = getattr(inspection, 'health', None)
    if health in {LeaseHealth.MISSING, LeaseHealth.UNMOUNTED}:
        return 'unmounted'
    if health is LeaseHealth.HEALTHY:
        return 'mounted'
    return 'failed'


def _desired_state(inspection) -> str:
    desired_state = str(getattr(inspection, 'desired_state', '') or '').strip()
    if desired_state:
        return desired_state
    return 'running'


__all__ = [
    'DaemonStartState',
    'finalize_daemon_start',
    'poll_daemon_start_iteration',
]
