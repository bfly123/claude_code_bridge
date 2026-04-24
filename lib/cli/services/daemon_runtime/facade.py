from __future__ import annotations

from ccbd.services.mount import MountManager
from ccbd.services.ownership import OwnershipGuard
from cli.kill_runtime.processes import is_pid_alive

from .keeper import ensure_keeper_started as ensure_keeper_started_runtime
from .keeper import keeper_pid as keeper_pid_runtime
from .keeper import wait_for_keeper_exit as wait_for_keeper_exit_runtime
from .policy import (
    KEEPER_READY_TIMEOUT_S,
    STARTUP_PROGRESS_STALL_TIMEOUT_S,
    STARTUP_TRANSACTION_TIMEOUT_S,
)
from .processes import (
    should_restart_unreachable_daemon as should_restart_unreachable_daemon_runtime,
)
from .processes import spawn_ccbd as spawn_ccbd_runtime

SHUTDOWN_TIMEOUT_S = 2.0
START_TIMEOUT_S = STARTUP_TRANSACTION_TIMEOUT_S


def incompatible_daemon_error() -> str:
    return 'mounted ccbd config does not match current .ccb/ccb.config'


def ensure_keeper_started(context) -> bool:
    return ensure_keeper_started_runtime(
        context,
        mount_manager_factory=MountManager,
        ownership_guard_factory=OwnershipGuard,
        process_exists_fn=is_pid_alive,
        ready_timeout_s=KEEPER_READY_TIMEOUT_S,
    )


def wait_for_keeper_exit(context, *, timeout_s: float) -> bool:
    return wait_for_keeper_exit_runtime(
        context,
        timeout_s=timeout_s,
        process_exists_fn=is_pid_alive,
    )


def keeper_pid(context, lease) -> int:
    return keeper_pid_runtime(
        context,
        lease,
        process_exists_fn=is_pid_alive,
    )


def should_restart_unreachable_daemon(inspection) -> bool:
    return should_restart_unreachable_daemon_runtime(inspection)


def spawn_ccbd_process(context) -> None:
    spawn_ccbd_runtime(context, start_timeout_s=STARTUP_TRANSACTION_TIMEOUT_S)


__all__ = [
    'KEEPER_READY_TIMEOUT_S',
    'STARTUP_PROGRESS_STALL_TIMEOUT_S',
    'SHUTDOWN_TIMEOUT_S',
    'START_TIMEOUT_S',
    'STARTUP_TRANSACTION_TIMEOUT_S',
    'ensure_keeper_started',
    'incompatible_daemon_error',
    'keeper_pid',
    'should_restart_unreachable_daemon',
    'spawn_ccbd_process',
    'wait_for_keeper_exit',
]
