from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from provider_core.runtime_specs import provider_env_name


def check_all_sessions(
    registry,
    *,
    env_float_fn: Callable[[str, float], float],
    env_int_fn: Callable[[str, int], int],
) -> None:
    now = time.time()
    refresh_interval_s = env_float_fn(provider_env_name('claude', 'BIND_REFRESH_INTERVAL'), 60.0)
    scan_limit = max(50, min(20000, env_int_fn(provider_env_name('claude', 'BIND_SCAN_LIMIT'), 400)))
    snapshot = _session_snapshot(registry)
    for key, work_dir in snapshot:
        try:
            registry._check_one(key, work_dir, now=now, refresh_interval_s=refresh_interval_s, scan_limit=scan_limit)
        except Exception:
            continue
    release_stale_work_dirs(registry, now=now)


def _session_snapshot(registry) -> list[tuple[str, Path]]:
    with registry._lock:
        return [(key, entry.work_dir) for key, entry in registry._sessions.items() if entry.valid]


def release_stale_work_dirs(registry, *, now: float) -> None:
    with registry._lock:
        keys_to_remove: list[str] = []
        removed_work_dirs: list[Path] = []
        for key, entry in list(registry._sessions.items()):
            if not entry.valid and now - entry.last_check > 300:
                keys_to_remove.append(key)
                removed_work_dirs.append(entry.work_dir)
        for key in keys_to_remove:
            del registry._sessions[key]
    for work_dir in removed_work_dirs:
        registry._release_watchers_for_work_dir(work_dir, str(work_dir))


__all__ = ['check_all_sessions', 'release_stale_work_dirs']
