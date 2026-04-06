from __future__ import annotations

import time
from pathlib import Path

from terminal_runtime.env import env_float, env_int

_LAST_PANE_LOG_CLEAN: float = 0.0


def cleanup_pane_logs(dir_path: Path) -> None:
    global _LAST_PANE_LOG_CLEAN
    interval_s = env_float('CCB_PANE_LOG_CLEAN_INTERVAL_S', 600.0)
    now = time.time()
    if interval_s and (now - _LAST_PANE_LOG_CLEAN) < interval_s:
        return
    _LAST_PANE_LOG_CLEAN = now

    ttl_days = env_int('CCB_PANE_LOG_TTL_DAYS', 7)
    max_files = env_int('CCB_PANE_LOG_MAX_FILES', 200)
    if ttl_days <= 0 and max_files <= 0:
        return
    try:
        if not dir_path.exists():
            return
    except Exception:
        return
    files = list_log_files(dir_path)
    if ttl_days > 0:
        files = drop_expired_logs(files, now=now, ttl_days=ttl_days)
    if max_files > 0 and len(files) > max_files:
        trim_extra_logs(files, max_files=max_files)


def list_log_files(dir_path: Path) -> list[Path]:
    files: list[Path] = []
    try:
        for entry in dir_path.iterdir():
            if entry.is_file():
                files.append(entry)
    except Exception:
        return []
    return files


def drop_expired_logs(files: list[Path], *, now: float, ttl_days: int) -> list[Path]:
    cutoff = now - (ttl_days * 86400)
    remaining = list(files)
    for path in list(remaining):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                remaining.remove(path)
        except Exception:
            continue
    return remaining


def trim_extra_logs(files: list[Path], *, max_files: int) -> None:
    try:
        files.sort(key=lambda path: path.stat().st_mtime)
    except Exception:
        files.sort(key=lambda path: path.name)
    extra = len(files) - max_files
    for path in files[:extra]:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            continue


__all__ = ['cleanup_pane_logs', 'drop_expired_logs', 'list_log_files', 'trim_extra_logs']
