from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import time

from agents.config_identity import project_config_identity_payload
from agents.config_loader import load_project_config
from ccbd.daemon_process import CcbdProcessError, spawn_ccbd_process
from ccbd.keeper import (
    KeeperStateStore,
    ShutdownIntent,
    ShutdownIntentStore,
    keeper_state_is_running,
)
from ccbd.models import LeaseHealth
from ccbd.services.mount import MountManager
from ccbd.services.ownership import OwnershipGuard
from ccbd.socket_client import CcbdClient, CcbdClientError
from ccbd.system import utc_now
from cli.kill_runtime.processes import is_pid_alive, kill_pid, terminate_pid_tree
from cli.context import CliContext
from .daemon_runtime import (
    CcbdServiceError,
    DaemonHandle,
    KillSummary,
    LocalPingSummary,
)
from .daemon_runtime import connect_mounted_daemon as _connect_mounted_daemon_runtime
from .daemon_runtime import ensure_daemon_started as _ensure_daemon_started_runtime
from .daemon_runtime import shutdown_daemon as _shutdown_daemon_runtime


_DEF_START_TIMEOUT_S = 5.0
_DEF_SHUTDOWN_TIMEOUT_S = 2.0
_DEF_KEEPER_READY_TIMEOUT_S = 2.0


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
    if not inspection.socket_connectable:
        return None
    client = CcbdClient(context.paths.ccbd_socket_path)
    if _daemon_matches_project_config(context, client):
        return DaemonHandle(client=client, inspection=inspection, started=False)
    if not restart_on_mismatch:
        return None
    _shutdown_incompatible_daemon(context, client)
    return None


def _daemon_matches_project_config(context: CliContext, client: CcbdClient) -> bool:
    expected = project_config_identity_payload(load_project_config(context.project.project_root).config)
    try:
        payload = client.ping('ccbd')
    except CcbdClientError:
        return False
    actual_signature = str(payload.get('config_signature') or '').strip()
    if actual_signature:
        return actual_signature == expected['config_signature']
    known_agents = payload.get('known_agents')
    if not isinstance(known_agents, list):
        return False
    actual_agents = tuple(str(item).strip().lower() for item in known_agents if str(item).strip())
    return actual_agents == tuple(expected['known_agents'])


def _shutdown_incompatible_daemon(context: CliContext, client: CcbdClient) -> None:
    try:
        client.shutdown()
    except CcbdClientError:
        pass
    deadline = time.time() + _DEF_SHUTDOWN_TIMEOUT_S
    while time.time() < deadline:
        _, _, inspection = inspect_daemon(context)
        if not inspection.socket_connectable or inspection.health in {LeaseHealth.MISSING, LeaseHealth.UNMOUNTED, LeaseHealth.STALE}:
            return
        time.sleep(0.05)
    raise CcbdServiceError(f'{_incompatible_daemon_error()}; old ccbd did not shut down in time')


def _incompatible_daemon_error() -> str:
    return 'mounted ccbd config does not match current .ccb/ccb.config'


def _should_restart_unreachable_daemon(inspection) -> bool:
    return (
        inspection.health is LeaseHealth.DEGRADED
        and inspection.pid_alive
        and not inspection.socket_connectable
    )


def _restart_unreachable_daemon(context: CliContext, inspection) -> None:
    lease = inspection.lease
    if lease is None:
        return
    pid = _lease_pid(lease)
    manager = MountManager(context.paths)

    if pid > 0 and inspection.pid_alive:
        kill_pid(pid, force=False)
        if _wait_for_daemon_release(context, timeout_s=_DEF_SHUTDOWN_TIMEOUT_S):
            manager.mark_unmounted()
            return
        kill_pid(pid, force=True)
        if _wait_for_daemon_release(context, timeout_s=_DEF_SHUTDOWN_TIMEOUT_S):
            manager.mark_unmounted()
            return
        raise CcbdServiceError(f'ccbd is unavailable: {inspection.reason}; pid {pid} did not exit')


def _ensure_keeper_started(context: CliContext) -> bool:
    store = KeeperStateStore(context.paths)
    state = store.load()
    if keeper_state_is_running(state, process_exists_fn=is_pid_alive):
        return True

    manager = MountManager(context.paths)
    guard = OwnershipGuard(context.paths, manager)
    with guard.startup_lock():
        state = store.load()
        if keeper_state_is_running(state, process_exists_fn=is_pid_alive):
            return True
        _spawn_keeper_process(context)
    return _wait_for_keeper_ready(context, timeout_s=_DEF_KEEPER_READY_TIMEOUT_S)


def clear_shutdown_intent(context: CliContext) -> None:
    ShutdownIntentStore(context.paths).clear()


def record_shutdown_intent(context: CliContext, *, reason: str) -> None:
    ShutdownIntentStore(context.paths).save(
        ShutdownIntent(
            project_id=context.project.project_id,
            requested_at=utc_now(),
            requested_by_pid=os.getpid(),
            reason=reason,
        )
    )


def _wait_for_keeper_ready(context: CliContext, *, timeout_s: float) -> bool:
    deadline = time.time() + max(0.0, float(timeout_s))
    store = KeeperStateStore(context.paths)
    while time.time() < deadline:
        if keeper_state_is_running(store.load(), process_exists_fn=is_pid_alive):
            return True
        time.sleep(0.05)
    return keeper_state_is_running(store.load(), process_exists_fn=is_pid_alive)


def _wait_for_keeper_exit(context: CliContext, *, timeout_s: float) -> bool:
    deadline = time.time() + max(0.0, float(timeout_s))
    store = KeeperStateStore(context.paths)
    while time.time() < deadline:
        state = store.load()
        if not keeper_state_is_running(state, process_exists_fn=is_pid_alive):
            return True
        time.sleep(0.05)
    state = store.load()
    return not keeper_state_is_running(state, process_exists_fn=is_pid_alive)


def _keeper_pid(context: CliContext, lease) -> int:
    state = KeeperStateStore(context.paths).load()
    if keeper_state_is_running(state, process_exists_fn=is_pid_alive):
        return int(state.keeper_pid)
    lease_keeper_pid = int(getattr(lease, 'keeper_pid', 0) or 0)
    return lease_keeper_pid if lease_keeper_pid > 0 else 0


def _lease_pid(lease) -> int:
    return int(getattr(lease, 'ccbd_pid', 0) or 0)


def _wait_for_daemon_release(context: CliContext, *, timeout_s: float) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        _, _, inspection = inspect_daemon(context)
        if not inspection.pid_alive or inspection.health in {LeaseHealth.MISSING, LeaseHealth.UNMOUNTED, LeaseHealth.STALE}:
            return True
        time.sleep(0.05)
    return False


def _wait_for_pid_exit(pid: int, *, timeout_s: float) -> bool:
    deadline = time.time() + max(0.0, float(timeout_s))
    while time.time() < deadline:
        if not is_pid_alive(pid):
            return True
        time.sleep(0.05)
    return not is_pid_alive(pid)


def _spawn_ccbd_process(context: CliContext) -> None:
    try:
        spawn_ccbd_process(
            project_root=context.project.project_root,
            socket_path=context.paths.ccbd_socket_path,
            ccbd_dir=context.paths.ccbd_dir,
            timeout_s=_DEF_START_TIMEOUT_S,
        )
    except CcbdProcessError as exc:
        raise CcbdServiceError(str(exc)) from exc


def _spawn_keeper_process(context: CliContext) -> None:
    script = Path(__file__).resolve().parents[2] / 'ccbd' / 'keeper_main.py'
    env = dict(os.environ)
    env['PYTHONUNBUFFERED'] = '1'
    lib_root = str(Path(__file__).resolve().parents[2])
    current_pythonpath = env.get('PYTHONPATH')
    env['PYTHONPATH'] = lib_root if not current_pythonpath else lib_root + os.pathsep + current_pythonpath
    context.paths.ccbd_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = open(context.paths.ccbd_dir / 'keeper.stdout.log', 'ab')
    stderr_log = open(context.paths.ccbd_dir / 'keeper.stderr.log', 'ab')
    subprocess.Popen(
        [sys.executable, str(script), '--project', str(context.project.project_root)],
        cwd=str(context.project.project_root),
        env=env,
        stdout=stdout_log,
        stderr=stderr_log,
        start_new_session=True,
    )
