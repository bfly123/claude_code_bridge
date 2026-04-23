from __future__ import annotations

import csv
import os
import signal
import subprocess
import time
from collections.abc import Callable


def _system32_executable(name: str) -> str:
    return os.path.join(os.environ.get('SystemRoot', r'C:\WINDOWS'), 'System32', name)


def kill_pid(pid: int, *, force: bool = False) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            if not _windows_pid_safe_to_terminate(pid):
                return False
            if force:
                subprocess.run([_system32_executable("taskkill.exe"), "/F", "/PID", str(pid)], capture_output=True)
            else:
                subprocess.run([_system32_executable("taskkill.exe"), "/PID", str(pid)], capture_output=True)
        else:
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
        return True
    except Exception:
        return False


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        return _windows_pid_exists(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _windows_pid_exists(pid: int) -> bool:
    try:
        result = subprocess.run(
            [_system32_executable("tasklist.exe"), "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return False
    if result.returncode != 0:
        return False
    rows = [row for row in csv.reader((result.stdout or "").splitlines()) if row]
    return any(len(row) > 1 and row[1].strip().strip('\"') == str(int(pid)) for row in rows)


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
    if not _windows_pid_safe_to_terminate(pid):
        return False
    try:
        subprocess.run(_taskkill_tree_args(pid, force=force), capture_output=True)
        return True
    except Exception:
        return False


def _taskkill_tree_args(pid: int, *, force: bool) -> list[str]:
    args = [_system32_executable("taskkill.exe"), "/T", "/PID", str(pid)]
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


def _windows_pid_safe_to_terminate(pid: int) -> bool:
    if os.name != 'nt':
        return True
    if pid <= 0:
        return False
    protected = _windows_protected_pids()
    if pid in protected:
        return False
    lineage = _windows_ancestor_chain(pid)
    return os.getpid() in lineage


def _windows_protected_pids() -> set[int]:
    current_pid = int(os.getpid() or 0)
    protected = {current_pid}
    try:
        parent_pid = int(os.getppid() or 0)
    except Exception:
        parent_pid = 0
    if parent_pid > 0:
        protected.add(parent_pid)
    protected.update(_windows_ancestor_chain(current_pid))
    return {value for value in protected if value > 0}


def _windows_ancestor_chain(pid: int, *, max_depth: int = 32) -> tuple[int, ...]:
    lineage: list[int] = []
    seen: set[int] = set()
    current = int(pid or 0)
    while current > 0 and current not in seen and len(lineage) < max_depth:
        lineage.append(current)
        seen.add(current)
        parent = _windows_process_parent_pid(current)
        if parent is None or parent <= 0 or parent == current:
            break
        current = parent
    return tuple(lineage)


def _windows_process_parent_pid(pid: int) -> int | None:
    if os.name != 'nt' or pid <= 0:
        return None
    command = f"$p = Get-CimInstance Win32_Process -Filter \"ProcessId={int(pid)}\"; if ($p) {{ [Console]::Out.Write($p.ParentProcessId) }}"
    try:
        result = subprocess.run(
            [_system32_executable("WindowsPowerShell\\v1.0\\powershell.exe"), "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    text = str(result.stdout or '').strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


__all__ = ["is_pid_alive", "kill_pid", "terminate_pid_tree"]
