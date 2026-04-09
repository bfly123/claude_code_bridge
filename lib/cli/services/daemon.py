from __future__ import annotations

from ccbd.models import LeaseHealth
from ccbd.services.mount import MountManager
from ccbd.services.ownership import OwnershipGuard
from ccbd.socket_client import CcbdClient, CcbdClientError
from cli.kill_runtime.processes import is_pid_alive, kill_pid, terminate_pid_tree
from cli.context import CliContext
from .daemon_runtime import (
    CcbdServiceError,
    DaemonHandle,
    KillSummary,
    LocalPingSummary,
)
from .daemon_runtime.compat import (
    connect_compatible_daemon as _connect_compatible_daemon_runtime_impl,
)
from .daemon_runtime.compat import (
    daemon_matches_project_config as _daemon_matches_project_config,
)
from .daemon_runtime.compat import (
    shutdown_incompatible_daemon as _shutdown_incompatible_daemon_runtime_impl,
)
from .daemon_runtime.keeper import clear_shutdown_intent
from .daemon_runtime.keeper import ensure_keeper_started as _ensure_keeper_started_runtime_impl
from .daemon_runtime.keeper import keeper_pid as _keeper_pid_runtime_impl
from .daemon_runtime.keeper import record_shutdown_intent
from .daemon_runtime.keeper import wait_for_keeper_exit as _wait_for_keeper_exit_runtime_impl
from .daemon_runtime.facade import incompatible_daemon_error as _incompatible_daemon_error_impl
from .daemon_runtime.facade import should_restart_unreachable_daemon as _should_restart_unreachable_daemon
from .daemon_runtime.facade import spawn_ccbd_process as _spawn_ccbd_process
from .daemon_runtime.processes import lease_pid as _lease_pid
from .daemon_runtime.processes import restart_unreachable_daemon as _restart_unreachable_daemon_runtime_impl
from .daemon_runtime.processes import wait_for_pid_exit as _wait_for_pid_exit
from .daemon_runtime import connect_mounted_daemon as _connect_mounted_daemon_runtime
from .daemon_runtime import ensure_daemon_started as _ensure_daemon_started_runtime
from .daemon_runtime import shutdown_daemon as _shutdown_daemon_runtime

from .daemon_runtime.facade import SHUTDOWN_TIMEOUT_S as _DEF_SHUTDOWN_TIMEOUT_S
from .daemon_runtime.facade import START_TIMEOUT_S as _DEF_START_TIMEOUT_S


def inspect_daemon(context: CliContext):
    manager = MountManager(context.paths)
    guard = OwnershipGuard(context.paths, manager)
    return manager, guard, guard.inspect()


def ensure_daemon_started(context: CliContext) -> DaemonHandle:
    return _ensure_daemon_started_runtime(
        context,
        clear_shutdown_intent_fn=clear_shutdown_intent,
        ensure_keeper_started_fn=_ensure_keeper_started,
        inspect_daemon_fn=inspect_daemon,
        connect_compatible_daemon_fn=_connect_compatible_daemon,
        should_restart_unreachable_daemon_fn=_should_restart_unreachable_daemon,
        restart_unreachable_daemon_fn=_restart_unreachable_daemon,
        spawn_ccbd_process_fn=_spawn_ccbd_process,
        incompatible_daemon_error_fn=_incompatible_daemon_error,
        start_timeout_s=_DEF_START_TIMEOUT_S,
    )


def connect_mounted_daemon(context: CliContext, *, allow_restart_stale: bool) -> DaemonHandle:
    return _connect_mounted_daemon_runtime(
        context,
        allow_restart_stale=allow_restart_stale,
        inspect_daemon_fn=inspect_daemon,
        connect_compatible_daemon_fn=_connect_compatible_daemon,
        ensure_daemon_started_fn=ensure_daemon_started,
        should_restart_unreachable_daemon_fn=_should_restart_unreachable_daemon,
        incompatible_daemon_error_fn=_incompatible_daemon_error,
    )


def ping_local_state(context: CliContext) -> LocalPingSummary:
    _, _, inspection = inspect_daemon(context)
    lease = inspection.lease
    return LocalPingSummary(
        project_id=context.project.project_id,
        mount_state=lease.mount_state.value if lease is not None else 'unmounted',
        health=inspection.health.value,
        generation=lease.generation if lease else None,
        socket_path=lease.socket_path if lease else None,
        last_heartbeat_at=lease.last_heartbeat_at if lease else None,
        pid_alive=inspection.pid_alive,
        socket_connectable=inspection.socket_connectable,
        heartbeat_fresh=inspection.heartbeat_fresh,
        takeover_allowed=inspection.takeover_allowed,
        reason=inspection.reason,
    )


def refresh_agent_health(context: CliContext) -> None:
    try:
        handle = connect_mounted_daemon(context, allow_restart_stale=False)
    except CcbdServiceError:
        return
    client = handle.client
    if client is None:
        return
    try:
        client.ping('all')
    except CcbdClientError:
        return


def shutdown_daemon(context: CliContext, *, force: bool) -> KillSummary:
    return _shutdown_daemon_runtime(
        context,
        force=force,
        record_shutdown_intent_fn=record_shutdown_intent,
        inspect_daemon_fn=inspect_daemon,
        client_factory=lambda current: CcbdClient(current.paths.ccbd_socket_path),
        lease_pid_fn=_lease_pid,
        keeper_pid_fn=_keeper_pid,
        wait_for_pid_exit_fn=_wait_for_pid_exit,
        wait_for_keeper_exit_fn=_wait_for_keeper_exit,
        is_pid_alive_fn=is_pid_alive,
        terminate_pid_tree_fn=terminate_pid_tree,
        shutdown_timeout_s=_DEF_SHUTDOWN_TIMEOUT_S,
    )


def _connect_compatible_daemon(
    context: CliContext,
    inspection,
    *,
    restart_on_mismatch: bool,
) -> DaemonHandle | None:
    return _connect_compatible_daemon_runtime_impl(
        context,
        inspection,
        restart_on_mismatch=restart_on_mismatch,
        client_factory=CcbdClient,
        daemon_matches_project_config_fn=_daemon_matches_project_config,
        shutdown_incompatible_daemon_fn=_shutdown_incompatible_daemon,
    )


def _shutdown_incompatible_daemon(context: CliContext, client: CcbdClient) -> None:
    _shutdown_incompatible_daemon_runtime_impl(
        context,
        client,
        inspect_daemon_fn=inspect_daemon,
        incompatible_daemon_error=_incompatible_daemon_error(),
        shutdown_timeout_s=_DEF_SHUTDOWN_TIMEOUT_S,
        unavailable_health_states={
            LeaseHealth.MISSING,
            LeaseHealth.UNMOUNTED,
            LeaseHealth.STALE,
        },
    )


def _incompatible_daemon_error() -> str:
    return _incompatible_daemon_error_impl()


def _ensure_keeper_started(context: CliContext) -> bool:
    return _ensure_keeper_started_runtime_impl(
        context,
        mount_manager_factory=MountManager,
        ownership_guard_factory=OwnershipGuard,
        process_exists_fn=is_pid_alive,
        ready_timeout_s=2.0,
    )


def _wait_for_keeper_exit(context: CliContext, *, timeout_s: float) -> bool:
    return _wait_for_keeper_exit_runtime_impl(
        context,
        timeout_s=timeout_s,
        process_exists_fn=is_pid_alive,
    )


def _keeper_pid(context: CliContext, lease) -> int:
    return _keeper_pid_runtime_impl(
        context,
        lease,
        process_exists_fn=is_pid_alive,
    )


def _restart_unreachable_daemon(context: CliContext, inspection) -> None:
    _restart_unreachable_daemon_runtime_impl(
        context,
        inspection,
        shutdown_timeout_s=_DEF_SHUTDOWN_TIMEOUT_S,
        inspect_daemon_fn=inspect_daemon,
        manager_factory=MountManager,
        kill_pid_fn=kill_pid,
    )
