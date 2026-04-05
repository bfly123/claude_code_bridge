from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import platform
import socket


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


def process_exists(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except Exception:
        return False
    return True


def unix_socket_connectable(path: str | Path, *, timeout_s: float = 0.2) -> bool:
    target = Path(path)
    if not target.exists() or not hasattr(socket, 'AF_UNIX'):
        return False
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout_s)
    try:
        sock.connect(str(target))
        return True
    except OSError:
        return False
    finally:
        sock.close()


__all__ = [
    'current_uid',
    'parse_utc_timestamp',
    'process_exists',
    'read_boot_id',
    'unix_socket_connectable',
    'utc_now',
]
