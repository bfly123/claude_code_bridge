from __future__ import annotations

from ccbd.socket_client import CcbdClientError

from .models import CcbdServiceError, KillSummary


def _request_shutdown_or_mark_unmounted(
    context,
    *,
    inspection,
    manager,
    force: bool,
    client_factory,
) -> None:
    if inspection.socket_connectable:
        try:
            client_factory(context).shutdown()
        except CcbdClientError as exc:
            if not force:
                raise CcbdServiceError(str(exc)) from exc
    else:
        manager.mark_unmounted()


def _wait_for_daemon_shutdown(
    *,
    daemon_pid: int,
    inspection,
    manager,
    shutdown_timeout_s: float,
    wait_for_pid_exit_fn,
    terminate_pid_tree_fn,
    is_pid_alive_fn,
) -> None:
    if daemon_pid <= 0 or not inspection.pid_alive:
        return
    if not wait_for_pid_exit_fn(daemon_pid, timeout_s=shutdown_timeout_s):
        terminate_pid_tree_fn(daemon_pid, timeout_s=shutdown_timeout_s, is_pid_alive_fn=is_pid_alive_fn)
    if not is_pid_alive_fn(daemon_pid):
        manager.mark_unmounted()


def _wait_for_keeper_shutdown(
    context,
    *,
    keeper_pid: int,
    shutdown_timeout_s: float,
    wait_for_keeper_exit_fn,
    terminate_pid_tree_fn,
    is_pid_alive_fn,
) -> None:
    if keeper_pid <= 0:
        return
    if not wait_for_keeper_exit_fn(context, timeout_s=shutdown_timeout_s):
        terminate_pid_tree_fn(keeper_pid, timeout_s=shutdown_timeout_s, is_pid_alive_fn=is_pid_alive_fn)


def _unlink_socket_if_forced(context, *, force: bool) -> None:
    if not force:
        return
    try:
        context.paths.ccbd_socket_path.unlink()
    except FileNotFoundError:
        pass


def shutdown_daemon(
    context,
    *,
    force: bool,
    record_shutdown_intent_fn,
    inspect_daemon_fn,
    client_factory,
    lease_pid_fn,
    keeper_pid_fn,
    wait_for_pid_exit_fn,
    wait_for_keeper_exit_fn,
    is_pid_alive_fn,
    terminate_pid_tree_fn,
    shutdown_timeout_s: float,
) -> KillSummary:
    record_shutdown_intent_fn(context, reason='kill')
    manager, _guard, inspection = inspect_daemon_fn(context)
    lease = inspection.lease
    daemon_pid = lease_pid_fn(lease)
    keeper_pid = keeper_pid_fn(context, lease)
    _request_shutdown_or_mark_unmounted(
        context,
        inspection=inspection,
        manager=manager,
        force=force,
        client_factory=client_factory,
    )
    _wait_for_daemon_shutdown(
        daemon_pid=daemon_pid,
        inspection=inspection,
        manager=manager,
        shutdown_timeout_s=shutdown_timeout_s,
        wait_for_pid_exit_fn=wait_for_pid_exit_fn,
        terminate_pid_tree_fn=terminate_pid_tree_fn,
        is_pid_alive_fn=is_pid_alive_fn,
    )
    _wait_for_keeper_shutdown(
        context,
        keeper_pid=keeper_pid,
        shutdown_timeout_s=shutdown_timeout_s,
        wait_for_keeper_exit_fn=wait_for_keeper_exit_fn,
        terminate_pid_tree_fn=terminate_pid_tree_fn,
        is_pid_alive_fn=is_pid_alive_fn,
    )
    _unlink_socket_if_forced(context, force=force)

    lease = manager.load_state()
    return KillSummary(
        project_id=context.project.project_id,
        state=lease.mount_state.value if lease is not None else 'unmounted',
        socket_path=str(context.paths.ccbd_socket_path),
        forced=force,
    )


__all__ = ['shutdown_daemon']
