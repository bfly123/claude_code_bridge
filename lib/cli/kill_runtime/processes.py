from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Callable


def kill_pid(pid: int, *, force: bool = False) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            if force:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            else:
                subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True)
        else:
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
        return True
    except Exception:
        return False


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def terminate_pid_tree(
    pid: int,
    *,
    timeout_s: float = 1.0,
    is_pid_alive_fn: Callable[[int], bool] = is_pid_alive,
) -> bool:
    if pid <= 0:
        return False
    if not is_pid_alive_fn(pid):
        return True

    if _kill_pid_tree_once(pid, force=False):
        if _wait_for_pid_exit(pid, timeout_s=timeout_s, is_pid_alive_fn=is_pid_alive_fn):
            return True

    if not is_pid_alive_fn(pid):
        return True

    if _kill_pid_tree_once(pid, force=True):
        if _wait_for_pid_exit(pid, timeout_s=max(timeout_s, 0.2), is_pid_alive_fn=is_pid_alive_fn):
            return True

    return not is_pid_alive_fn(pid)


def _kill_pid_tree_once(pid: int, *, force: bool) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        return _kill_pid_tree_windows(pid, force=force)
    return _kill_pid_tree_posix(pid, force=force)


def _kill_pid_tree_windows(pid: int, *, force: bool) -> bool:
    try:
        subprocess.run(_taskkill_tree_args(pid, force=force), capture_output=True)
        return True
    except Exception:
        return False


def _taskkill_tree_args(pid: int, *, force: bool) -> list[str]:
    args = ["taskkill", "/T", "/PID", str(pid)]
    if force:
        args.insert(1, "/F")
    return args


def _kill_pid_tree_posix(pid: int, *, force: bool) -> bool:
    sig = signal.SIGKILL if force else signal.SIGTERM
    if _kill_process_group(pid, sig):
        return True
    return kill_pid(pid, force=force)


def _kill_process_group(pid: int, sig: signal.Signals) -> bool:
    pgid = _safe_getpgid(pid)
    current_pgid = _safe_getpgrp()
    if pgid is None or pgid <= 1 or pgid == current_pgid:
        return False
    try:
        os.killpg(pgid, sig)
        return True
    except Exception:
        return False


def _wait_for_pid_exit(pid: int, *, timeout_s: float, is_pid_alive_fn: Callable[[int], bool]) -> bool:
    deadline = time.time() + max(0.0, float(timeout_s))
    while time.time() < deadline:
        if not is_pid_alive_fn(pid):
            return True
        time.sleep(0.05)
    return not is_pid_alive_fn(pid)


def _safe_getpgid(pid: int) -> int | None:
    try:
        return os.getpgid(pid)
    except Exception:
        return None


def _safe_getpgrp() -> int | None:
    try:
        return os.getpgrp()
    except Exception:
        return None


__all__ = ["is_pid_alive", "kill_pid", "terminate_pid_tree"]
