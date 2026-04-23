from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
import os
import platform
import subprocess

from ccbd.ipc import endpoint_connectable


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_utc_timestamp(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith('Z'):
        normalized = normalized[:-1] + '+00:00'
    return datetime.fromisoformat(normalized)


def current_uid() -> int:
    getter = getattr(os, 'getuid', None)
    if getter is None:
        return -1
    try:
        return int(getter())
    except Exception:
        return -1


def read_boot_id() -> str:
    boot_path = Path('/proc/sys/kernel/random/boot_id')
    try:
        if boot_path.exists():
            value = boot_path.read_text(encoding='utf-8').strip()
            if value:
                return value
    except Exception:
        pass
    return platform.node() or 'unknown-boot'


def _system32_executable(name: str) -> str:
    return os.path.join(os.environ.get('SystemRoot', r'C:\WINDOWS'), 'System32', name)


def process_exists(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    if os.name == 'nt':
        return _windows_pid_exists(int(pid))
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except Exception:
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


def unix_socket_connectable(path: str | Path, *, timeout_s: float = 0.2) -> bool:
    return endpoint_connectable(path, timeout_s=timeout_s, ipc_kind='unix_socket')


def ipc_endpoint_connectable(path: str | Path, *, timeout_s: float = 0.2, ipc_kind: str | None = None) -> bool:
    return endpoint_connectable(path, timeout_s=timeout_s, ipc_kind=ipc_kind)


__all__ = [
    'current_uid',
    'ipc_endpoint_connectable',
    'parse_utc_timestamp',
    'process_exists',
    'read_boot_id',
    'unix_socket_connectable',
    'utc_now',
]
