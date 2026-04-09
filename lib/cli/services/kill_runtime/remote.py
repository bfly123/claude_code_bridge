from __future__ import annotations

import time


def request_remote_stop(
    context,
    *,
    force: bool,
    connect_mounted_daemon_fn,
    record_shutdown_intent_fn,
    ccbd_client_cls,
    summary_from_stop_all_payload_fn,
    stop_all_timeout_s: float,
    service_error_cls,
):
    try:
        handle = connect_mounted_daemon_fn(context, allow_restart_stale=False)
    except service_error_cls:
        return None
    if handle is None or handle.client is None:
        return None
    try:
        record_shutdown_intent_fn(context, reason='kill')
        stop_all_client = (
            ccbd_client_cls(context.paths.ccbd_socket_path, timeout_s=stop_all_timeout_s)
            if isinstance(handle.client, ccbd_client_cls)
            else handle.client
        )
        payload = stop_all_client.stop_all(force=force)
    except Exception:
        if not force:
            raise
        return None
    return summary_from_stop_all_payload_fn(payload)


def resolve_shutdown_summary(
    context,
    *,
    remote_summary,
    force: bool,
    shutdown_daemon_fn,
    await_remote_shutdown_fn,
    service_error_cls,
    kill_summary_cls,
):
    if remote_summary is not None:
        return await_remote_shutdown_fn(context, force=force)
    try:
        return shutdown_daemon_fn(context, force=force)
    except service_error_cls:
        if not force:
            raise
        return kill_summary_cls(
            project_id=context.project.project_id,
            state='unmounted',
            socket_path=str(context.paths.ccbd_socket_path),
            forced=force,
        )


def await_remote_shutdown(
    context,
    *,
    force: bool,
    inspect_daemon_fn,
    lease_health_cls,
    kill_summary_cls,
    timeout_s: float = 2.5,
):
    deadline = time.time() + max(0.1, float(timeout_s))
    last_inspection = None
    while time.time() < deadline:
        _, _, inspection = inspect_daemon_fn(context)
        last_inspection = inspection
        if not inspection.socket_connectable and inspection.health in {
            lease_health_cls.MISSING,
            lease_health_cls.UNMOUNTED,
            lease_health_cls.STALE,
        }:
            break
        time.sleep(0.05)
    lease = None if last_inspection is None else last_inspection.lease
    return kill_summary_cls(
        project_id=context.project.project_id,
        state=lease.mount_state.value if lease is not None else 'unmounted',
        socket_path=str(context.paths.ccbd_socket_path),
        forced=force,
    )


__all__ = ['await_remote_shutdown', 'request_remote_stop', 'resolve_shutdown_summary']
