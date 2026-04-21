from __future__ import annotations

import time

from ccbd.daemon_process import CcbdProcessError, spawn_ccbd_process
from ccbd.models import LeaseHealth
from cli.kill_runtime.processes import is_pid_alive, kill_pid

from .lease import mark_inspected_lease_unmounted
from .models import CcbdServiceError


def should_restart_unreachable_daemon(inspection) -> bool:
    return (
        inspection.health is LeaseHealth.STALE
        and inspection.pid_alive
        and not inspection.socket_connectable
    )


def restart_unreachable_daemon(
    context,
    inspection,
    *,
    shutdown_timeout_s: float,
    inspect_daemon_fn,
    manager_factory,
    kill_pid_fn=kill_pid,
) -> None:
    lease = inspection.lease
    if lease is None:
        return
    pid = lease_pid(lease)
    manager = manager_factory(context.paths)

    if pid > 0 and inspection.pid_alive:
        kill_pid_fn(pid, force=False)
        if wait_for_daemon_release(
            context,
            timeout_s=shutdown_timeout_s,
            inspect_daemon_fn=inspect_daemon_fn,
        ):
            mark_inspected_lease_unmounted(manager, inspection)
            return
        kill_pid_fn(pid, force=True)
        if wait_for_daemon_release(
            context,
            timeout_s=shutdown_timeout_s,
            inspect_daemon_fn=inspect_daemon_fn,
        ):
            mark_inspected_lease_unmounted(manager, inspection)
            return
        raise CcbdServiceError(
            f'ccbd is unavailable: {inspection.reason}; pid {pid} did not exit'
        )


def lease_pid(lease) -> int:
    return int(getattr(lease, 'ccbd_pid', 0) or 0)


def wait_for_daemon_release(
    context,
    *,
    timeout_s: float,
    inspect_daemon_fn,
) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        _, _, inspection = inspect_daemon_fn(context)
        if not inspection.pid_alive or inspection.health in {
            LeaseHealth.MISSING,
            LeaseHealth.UNMOUNTED,
            LeaseHealth.STALE,
        }:
            return True
        time.sleep(0.05)
    return False


def wait_for_pid_exit(pid: int, *, timeout_s: float) -> bool:
    deadline = time.time() + max(0.0, float(timeout_s))
    while time.time() < deadline:
        if not is_pid_alive(pid):
            return True
        time.sleep(0.05)
    return not is_pid_alive(pid)


def spawn_ccbd(context, *, start_timeout_s: float) -> None:
    try:
        spawn_ccbd_process(
            project_root=context.project.project_root,
            socket_path=context.paths.ccbd_socket_path,
            ccbd_dir=context.paths.ccbd_dir,
            timeout_s=start_timeout_s,
        )
    except CcbdProcessError as exc:
        raise CcbdServiceError(str(exc)) from exc


__all__ = [
    'lease_pid',
    'restart_unreachable_daemon',
    'should_restart_unreachable_daemon',
    'spawn_ccbd',
    'wait_for_daemon_release',
    'wait_for_pid_exit',
]
