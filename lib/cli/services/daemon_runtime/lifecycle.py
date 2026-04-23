from __future__ import annotations

import os
import time

from ccbd.models import LeaseHealth

from .models import CcbdServiceError, DaemonHandle
from .lifecycle_start import DaemonStartState, finalize_daemon_start, poll_daemon_start_iteration


def ensure_daemon_started(
    context,
    *,
    clear_shutdown_intent_fn,
    ensure_keeper_started_fn,
    inspect_daemon_fn,
    connect_compatible_daemon_fn,
    should_restart_unreachable_daemon_fn,
    restart_unreachable_daemon_fn,
    spawn_ccbd_process_fn,
    incompatible_daemon_error_fn,
    start_timeout_s: float,
) -> DaemonHandle:
    clear_shutdown_intent_fn(context)
    state = DaemonStartState(keeper_started=bool(ensure_keeper_started_fn(context)))
    tolerate_interrupts = _should_tolerate_keyboard_interrupt(context)
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
            spawn_ccbd_process_fn=spawn_ccbd_process_fn,
        )
        if handle is not None:
            return handle
        _sleep(0.05, tolerate_interrupts=tolerate_interrupts)

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
    handle = connect_compatible_daemon_fn(context, inspection, restart_on_mismatch=allow_restart_stale)
    if handle is not None:
        return handle
    _manager, _guard, inspection = inspect_daemon_fn(context)
    if allow_restart_stale and (
        inspection.health in {LeaseHealth.MISSING, LeaseHealth.UNMOUNTED, LeaseHealth.STALE}
        or should_restart_unreachable_daemon_fn(inspection)
    ):
        return ensure_daemon_started_fn(context)
    if inspection.health is LeaseHealth.UNMOUNTED:
        raise CcbdServiceError('project ccbd is unmounted; run `ccb` first')
    if inspection.health is LeaseHealth.MISSING:
        raise CcbdServiceError('project ccbd is not mounted; run `ccb` first')
    if inspection.socket_connectable:
        handle = connect_compatible_daemon_fn(context, inspection, restart_on_mismatch=False)
        if handle is not None:
            return handle
        raise CcbdServiceError(incompatible_daemon_error_fn())
    raise CcbdServiceError(f'ccbd is unavailable: {inspection.reason}')


def _should_tolerate_keyboard_interrupt(context) -> bool:
    return os.name == 'nt' or getattr(context.paths, 'ccbd_ipc_kind', None) == 'named_pipe'


def _sleep(duration_s: float, *, tolerate_interrupts: bool) -> None:
    deadline = time.time() + max(0.0, float(duration_s))
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            return
        try:
            time.sleep(remaining)
            return
        except KeyboardInterrupt:
            if not tolerate_interrupts:
                raise


__all__ = ['connect_mounted_daemon', 'ensure_daemon_started']
