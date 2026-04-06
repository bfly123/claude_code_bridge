from __future__ import annotations

from pathlib import Path
from typing import Callable


def invalidate(
    registry,
    work_dir: Path,
    *,
    write_log_fn: Callable[[str], None],
    release_watchers_for_work_dir_fn: Callable[[Path, str], None],
) -> None:
    key = str(work_dir)
    with registry._lock:
        if key in registry._sessions:
            registry._sessions[key].valid = False
            write_log_fn(f'[INFO] Session invalidated: {work_dir}')
    release_watchers_for_work_dir_fn(work_dir, key)


def remove(
    registry,
    work_dir: Path,
    *,
    write_log_fn: Callable[[str], None],
    release_watchers_for_work_dir_fn: Callable[[Path, str], None],
) -> None:
    key = str(work_dir)
    with registry._lock:
        if key in registry._sessions:
            del registry._sessions[key]
            write_log_fn(f'[INFO] Session removed: {work_dir}')
    release_watchers_for_work_dir_fn(work_dir, key)


__all__ = ['invalidate', 'remove']
