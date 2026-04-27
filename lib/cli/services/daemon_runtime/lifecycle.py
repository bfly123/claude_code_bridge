from __future__ import annotations

from datetime import datetime, timezone
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
    progress_stall_timeout_s: float,
) -> DaemonHandle:
    clear_shutdown_intent_fn(context)
    startup_requested = bool(record_running_intent_fn(context))
    state = DaemonStartState(
        keeper_started=bool(ensure_keeper_started_fn(context)),
        started=startup_requested,
    )
    local_deadline = time.time() + max(0.0, float(start_timeout_s))

    while True:
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
        _, _, inspection = inspect_daemon_fn(context)
        if _startup_wait_exhausted(
            inspection,
            local_deadline=local_deadline,
            progress_stall_timeout_s=progress_stall_timeout_s,
        ):
            break
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


def _startup_wait_exhausted(
    inspection,
    *,
    local_deadline: float,
    progress_stall_timeout_s: float,
) -> bool:
    phase = _phase(inspection)
    now = time.time()
    if now >= local_deadline:
        return True
    if phase != 'starting':
        return False
    transaction_deadline = _timestamp_seconds(getattr(inspection, 'startup_deadline_at', None))
    if transaction_deadline is not None and now >= transaction_deadline:
        return True
    if progress_stall_timeout_s <= 0:
        return False
    last_progress = _timestamp_seconds(getattr(inspection, 'last_progress_at', None))
    if last_progress is None:
        return False
    return now >= last_progress + float(progress_stall_timeout_s)


def _timestamp_seconds(value: object) -> float | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        normalized = text[:-1] + '+00:00' if text.endswith('Z') else text
        parsed = datetime.fromisoformat(normalized)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


__all__ = ['connect_mounted_daemon', 'ensure_daemon_started']
