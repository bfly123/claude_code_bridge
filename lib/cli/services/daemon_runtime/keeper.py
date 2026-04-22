from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import time

from agents.config_identity import project_config_identity_payload
from agents.config_loader import load_project_config
from ccbd.keeper import (
    KeeperStateStore,
    ShutdownIntent,
    ShutdownIntentStore,
    keeper_state_is_running,
)
from ccbd.services.lifecycle import CcbdLifecycleStore, lifecycle_from_inspection
from ccbd.services.mount import MountManager
from ccbd.services.ownership import OwnershipGuard
from ccbd.system import utc_now
from runtime_env.control_plane import control_plane_env

from cli.kill_runtime.processes import is_pid_alive


def ensure_keeper_started(
    context,
    *,
    mount_manager_factory,
    ownership_guard_factory,
    process_exists_fn=is_pid_alive,
    spawn_keeper_process_fn=None,
    ready_timeout_s: float = 2.0,
) -> bool:
    store = KeeperStateStore(context.paths)
    state = store.load()
    if keeper_state_is_running(state, process_exists_fn=process_exists_fn):
        return True

    manager = mount_manager_factory(context.paths)
    guard = ownership_guard_factory(context.paths, manager)
    with guard.startup_lock():
        state = store.load()
        if keeper_state_is_running(state, process_exists_fn=process_exists_fn):
            return True
        (spawn_keeper_process_fn or spawn_keeper_process)(context)
    return wait_for_keeper_ready(
        context,
        timeout_s=ready_timeout_s,
        process_exists_fn=process_exists_fn,
    )


def clear_shutdown_intent(context) -> None:
    ShutdownIntentStore(context.paths).clear()


def record_running_intent(context) -> bool:
    store = CcbdLifecycleStore(context.paths)
    current = store.load()
    now = utc_now()
    if current is None:
        manager = MountManager(context.paths)
        current = lifecycle_from_inspection(
            project_id=context.project.project_id,
            inspection=OwnershipGuard(context.paths, manager).inspect(),
            occurred_at=now,
            config_signature=_current_config_signature(context),
        )
    startup_requested = current.desired_state != 'running' or current.phase != 'mounted'
    store.save(
        current.with_updates(
            desired_state='running',
            config_signature=_current_config_signature(context) or current.config_signature,
            socket_path=str(context.paths.ccbd_socket_path),
            last_failure_reason=None,
            shutdown_intent=None,
        )
    )
    return startup_requested


def record_shutdown_intent(context, *, reason: str) -> None:
    store = CcbdLifecycleStore(context.paths)
    current = store.load()
    now = utc_now()
    if current is None:
        manager = MountManager(context.paths)
        current = lifecycle_from_inspection(
            project_id=context.project.project_id,
            inspection=OwnershipGuard(context.paths, manager).inspect(),
            occurred_at=now,
            config_signature=_current_config_signature(context),
        )
    store.save(
        current.with_phase(
            'unmounted' if current.phase == 'unmounted' else 'stopping',
            occurred_at=now,
            desired_state='stopped',
            shutdown_intent=reason,
            last_failure_reason=None,
        )
    )
    ShutdownIntentStore(context.paths).save(
        ShutdownIntent(
            project_id=context.project.project_id,
            requested_at=now,
            requested_by_pid=os.getpid(),
            reason=reason,
        )
    )


def finalize_shutdown_lifecycle(context) -> None:
    store = CcbdLifecycleStore(context.paths)
    current = store.load()
    now = utc_now()
    if current is None:
        manager = MountManager(context.paths)
        current = lifecycle_from_inspection(
            project_id=context.project.project_id,
            inspection=OwnershipGuard(context.paths, manager).inspect(),
            occurred_at=now,
            config_signature=_current_config_signature(context),
        )
    store.save(
        current.with_phase(
            'unmounted',
            occurred_at=now,
            desired_state='stopped',
            owner_pid=None,
            owner_daemon_instance_id=None,
            socket_inode=None,
            socket_path=str(context.paths.ccbd_socket_path),
            last_failure_reason=None,
        )
    )


def wait_for_keeper_ready(
    context,
    *,
    timeout_s: float,
    process_exists_fn=is_pid_alive,
) -> bool:
    deadline = time.time() + max(0.0, float(timeout_s))
    store = KeeperStateStore(context.paths)
    while time.time() < deadline:
        if keeper_state_is_running(store.load(), process_exists_fn=process_exists_fn):
            return True
        time.sleep(0.05)
    return keeper_state_is_running(store.load(), process_exists_fn=process_exists_fn)


def wait_for_keeper_exit(
    context,
    *,
    timeout_s: float,
    process_exists_fn=is_pid_alive,
) -> bool:
    deadline = time.time() + max(0.0, float(timeout_s))
    store = KeeperStateStore(context.paths)
    while time.time() < deadline:
        state = store.load()
        if not keeper_state_is_running(state, process_exists_fn=process_exists_fn):
            return True
        time.sleep(0.05)
    state = store.load()
    return not keeper_state_is_running(state, process_exists_fn=process_exists_fn)


def keeper_pid(context, lease, *, process_exists_fn=is_pid_alive) -> int:
    state = KeeperStateStore(context.paths).load()
    if keeper_state_is_running(state, process_exists_fn=process_exists_fn):
        return int(state.keeper_pid)
    lease_keeper_pid = int(getattr(lease, 'keeper_pid', 0) or 0)
    return lease_keeper_pid if lease_keeper_pid > 0 else 0


def spawn_keeper_process(context) -> None:
    lib_root = _lib_root()
    script = lib_root / 'ccbd' / 'keeper_main.py'
    env = control_plane_env(extra={'PYTHONUNBUFFERED': '1'})
    current_pythonpath = env.get('PYTHONPATH')
    env['PYTHONPATH'] = (
        str(lib_root)
        if not current_pythonpath
        else str(lib_root) + os.pathsep + current_pythonpath
    )
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


def _lib_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _current_config_signature(context) -> str | None:
    try:
        config = load_project_config(context.project.project_root).config
    except Exception:
        return None
    return str(project_config_identity_payload(config)['config_signature'])


__all__ = [
    'clear_shutdown_intent',
    'ensure_keeper_started',
    'finalize_shutdown_lifecycle',
    'keeper_pid',
    'record_running_intent',
    'record_shutdown_intent',
    'spawn_keeper_process',
    'wait_for_keeper_exit',
    'wait_for_keeper_ready',
]
