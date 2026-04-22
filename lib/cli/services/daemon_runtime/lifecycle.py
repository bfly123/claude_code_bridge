from __future__ import annotations

import time

from ccbd.models import LeaseHealth

from .models import CcbdServiceError, DaemonHandle
from .lifecycle_start import DaemonStartState, finalize_daemon_start, poll_daemon_start_iteration


def ensure_daemon_started(
    context,
    *,
    clear_shutdown_intent_fn,
    record_running_intent_fn,
    ensure_keeper_started_fn,
    inspect_daemon_fn,
    connect_compatible_daemon_fn,
    should_restart_unreachable_daemon_fn,
    restart_unreachable_daemon_fn,
    incompatible_daemon_error_fn,
    start_timeout_s: float,
) -> DaemonHandle:
    clear_shutdown_intent_fn(context)
    startup_requested = bool(record_running_intent_fn(context))
    state = DaemonStartState(
        keeper_started=bool(ensure_keeper_started_fn(context)),
        started=startup_requested,
    )
    deadline = time.time() + start_timeout_s

    while time.time() < deadline:
        handle = poll_daemon_start_iteration(
            context,
            state=state,
            ensure_keeper_started_fn=ensure_keeper_started_fn,
            inspect_daemon_fn=inspect_daemon_fn,
            connect_compatible_daemon_fn=connect_compatible_daemon_fn,
            should_restart_unreachable_daemon_fn=should_restart_unreachable_daemon_fn,
            restart_unreachable_daemon_fn=restart_unreachable_daemon_fn,
        )
        if handle is not None:
            return handle
        time.sleep(0.05)

    return finalize_daemon_start(
        context,
        started=state.started,
        inspect_daemon_fn=inspect_daemon_fn,
        connect_compatible_daemon_fn=connect_compatible_daemon_fn,
        incompatible_daemon_error_fn=incompatible_daemon_error_fn,
    )


def connect_mounted_daemon(
    context,
    *,
    allow_restart_stale: bool,
    inspect_daemon_fn,
    connect_compatible_daemon_fn,
    ensure_daemon_started_fn,
    should_restart_unreachable_daemon_fn,
    incompatible_daemon_error_fn,
) -> DaemonHandle:
    _manager, _guard, inspection = inspect_daemon_fn(context)
    phase = _phase(inspection)
    if phase == 'mounted':
        handle = connect_compatible_daemon_fn(context, inspection, restart_on_mismatch=allow_restart_stale)
        if handle is not None:
            return handle
    _manager, _guard, inspection = inspect_daemon_fn(context)
    phase = _phase(inspection)
    if allow_restart_stale and _should_wait_or_recover(inspection, should_restart_unreachable_daemon_fn):
        return ensure_daemon_started_fn(context)
    if phase == 'unmounted':
        raise CcbdServiceError('project ccbd is unmounted; run `ccb` first')
    if phase == 'starting':
        raise CcbdServiceError('project ccbd is starting; wait for keeper to finish startup')
    if phase == 'stopping':
        raise CcbdServiceError('project ccbd is stopping; wait for shutdown to finish')
    if phase == 'mounted' and inspection.socket_connectable:
        handle = connect_compatible_daemon_fn(context, inspection, restart_on_mismatch=False)
        if handle is not None:
            return handle
        raise CcbdServiceError(incompatible_daemon_error_fn())
    failure_reason = str(getattr(inspection, 'last_failure_reason', '') or '').strip()
    if phase == 'failed' and failure_reason:
        raise CcbdServiceError(
            f'ccbd is unavailable: {inspection.reason}; lifecycle_failure: {failure_reason}'
        )
    raise CcbdServiceError(f'ccbd is unavailable: {inspection.reason}')


def _should_wait_or_recover(inspection, should_restart_unreachable_daemon_fn) -> bool:
    phase = _phase(inspection)
    if _desired_state(inspection) != 'running':
        return False
    if phase in {'unmounted', 'starting', 'failed'}:
        return True
    return (
        phase == 'mounted'
        and (
            inspection.health in {LeaseHealth.MISSING, LeaseHealth.UNMOUNTED, LeaseHealth.STALE}
            or should_restart_unreachable_daemon_fn(inspection)
        )
    )


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


__all__ = ['connect_mounted_daemon', 'ensure_daemon_started']
