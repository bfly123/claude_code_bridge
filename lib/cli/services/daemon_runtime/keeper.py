from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import time

from ccbd.keeper import (
    KeeperStateStore,
    ShutdownIntent,
    ShutdownIntentStore,
    keeper_state_is_running,
)
from ccbd.system import utc_now

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


def record_shutdown_intent(context, *, reason: str) -> None:
    ShutdownIntentStore(context.paths).save(
        ShutdownIntent(
            project_id=context.project.project_id,
            requested_at=utc_now(),
            requested_by_pid=os.getpid(),
            reason=reason,
        )
    )


def wait_for_keeper_ready(
    context,
    *,
    timeout_s: float,
    process_exists_fn=is_pid_alive,
) -> bool:
    tolerate_interrupts = _should_tolerate_keyboard_interrupt(context)
    deadline = _deadline_after(timeout_s, tolerate_interrupts=tolerate_interrupts)
    store = KeeperStateStore(context.paths)
    while not _deadline_expired(deadline, tolerate_interrupts=tolerate_interrupts):
        if keeper_state_is_running(store.load(), process_exists_fn=process_exists_fn):
            return True
        _sleep(0.05, tolerate_interrupts=tolerate_interrupts)
    return keeper_state_is_running(store.load(), process_exists_fn=process_exists_fn)


def wait_for_keeper_exit(
    context,
    *,
    timeout_s: float,
    process_exists_fn=is_pid_alive,
) -> bool:
    tolerate_interrupts = _should_tolerate_keyboard_interrupt(context)
    deadline = _deadline_after(timeout_s, tolerate_interrupts=tolerate_interrupts)
    store = KeeperStateStore(context.paths)
    while not _deadline_expired(deadline, tolerate_interrupts=tolerate_interrupts):
        state = store.load()
        if not keeper_state_is_running(state, process_exists_fn=process_exists_fn):
            return True
        _sleep(0.05, tolerate_interrupts=tolerate_interrupts)
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
    env = dict(os.environ)
    env['PYTHONUNBUFFERED'] = '1'
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


def _should_tolerate_keyboard_interrupt(context) -> bool:
    return os.name == 'nt' and getattr(context.paths, 'ccbd_ipc_kind', None) == 'named_pipe'


def _deadline_after(duration_s: float, *, tolerate_interrupts: bool) -> float:
    return _monotonic_now(tolerate_interrupts=tolerate_interrupts) + max(0.0, float(duration_s))


def _deadline_expired(deadline: float, *, tolerate_interrupts: bool) -> bool:
    return _monotonic_now(tolerate_interrupts=tolerate_interrupts) >= deadline


def _monotonic_now(*, tolerate_interrupts: bool) -> float:
    while True:
        try:
            return time.monotonic()
        except KeyboardInterrupt:
            if not tolerate_interrupts:
                raise


def _sleep(duration_s: float, *, tolerate_interrupts: bool) -> None:
    deadline = _deadline_after(duration_s, tolerate_interrupts=tolerate_interrupts)
    while True:
        remaining = deadline - _monotonic_now(tolerate_interrupts=tolerate_interrupts)
        if remaining <= 0:
            return
        try:
            time.sleep(remaining)
            return
        except KeyboardInterrupt:
            if not tolerate_interrupts:
                raise


__all__ = [
    'clear_shutdown_intent',
    'ensure_keeper_started',
    'keeper_pid',
    'record_shutdown_intent',
    'spawn_keeper_process',
    'wait_for_keeper_exit',
    'wait_for_keeper_ready',
]
