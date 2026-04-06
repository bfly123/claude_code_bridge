from __future__ import annotations

import time

from ccbd.models import LeaseHealth

from .models import CcbdServiceError, DaemonHandle


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
    keeper_started = bool(ensure_keeper_started_fn(context))
    started = False
    incompatible_restart_requested = False
    unreachable_restart_requested = False
    direct_spawn_requested = False
    deadline = time.time() + start_timeout_s

    while time.time() < deadline:
        _manager, _guard, inspection = inspect_daemon_fn(context)
        if inspection.socket_connectable:
            handle = connect_compatible_daemon_fn(
                context,
                inspection,
                restart_on_mismatch=not incompatible_restart_requested,
            )
            if handle is not None:
                return DaemonHandle(client=handle.client, inspection=inspection, started=started)
            if not incompatible_restart_requested:
                started = True
                incompatible_restart_requested = True
        elif should_restart_unreachable_daemon_fn(inspection) and not unreachable_restart_requested:
            restart_unreachable_daemon_fn(context, inspection)
            started = True
            unreachable_restart_requested = True
        elif inspection.health in {LeaseHealth.MISSING, LeaseHealth.UNMOUNTED, LeaseHealth.STALE}:
            started = True
            if keeper_started:
                # Project-scoped keeper owns daemon keepalive once it is active.
                # CLI should wait for keeper-driven spawn instead of double-spawning.
                pass
            elif not direct_spawn_requested:
                spawn_ccbd_process_fn(context)
                keeper_started = bool(ensure_keeper_started_fn(context))
                direct_spawn_requested = True
        time.sleep(0.05)

    _manager, _guard, inspection = inspect_daemon_fn(context)
    handle = connect_compatible_daemon_fn(context, inspection, restart_on_mismatch=False)
    if handle is not None:
        return DaemonHandle(client=handle.client, inspection=inspection, started=started)
    if inspection.socket_connectable:
        raise CcbdServiceError(incompatible_daemon_error_fn())
    raise CcbdServiceError(f'ccbd is unavailable: {inspection.reason}')


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
    if inspection.health is LeaseHealth.UNMOUNTED:
        raise CcbdServiceError('project ccbd is unmounted; run `ccb [agents...]` first')
    if inspection.health is LeaseHealth.MISSING:
        raise CcbdServiceError('project ccbd is not mounted; run `ccb [agents...]` first')
    if allow_restart_stale and (
        inspection.health is LeaseHealth.STALE or should_restart_unreachable_daemon_fn(inspection)
    ):
        return ensure_daemon_started_fn(context)
    if inspection.socket_connectable:
        handle = connect_compatible_daemon_fn(context, inspection, restart_on_mismatch=False)
        if handle is not None:
            return handle
        raise CcbdServiceError(incompatible_daemon_error_fn())
    raise CcbdServiceError(f'ccbd is unavailable: {inspection.reason}')


__all__ = ['connect_mounted_daemon', 'ensure_daemon_started']
