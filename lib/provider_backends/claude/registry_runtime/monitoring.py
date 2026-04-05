from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from provider_core.runtime_specs import provider_env_name


def start_monitor(registry) -> None:
    if registry._monitor_thread is None:
        registry._start_root_watcher()
        registry._monitor_thread = threading.Thread(target=registry._monitor_loop, daemon=True)
        registry._monitor_thread.start()


def stop_monitor(registry) -> None:
    registry._stop.set()
    registry._stop_root_watcher()
    registry._stop_all_watchers()


def monitor_loop(registry) -> None:
    while not registry._stop.wait(registry.CHECK_INTERVAL):
        registry._check_all_sessions()


def check_all_sessions(
    registry,
    *,
    env_float_fn: Callable[[str, float], float],
    env_int_fn: Callable[[str, int], int],
) -> None:
    now = time.time()
    refresh_interval_s = env_float_fn(provider_env_name("claude", "BIND_REFRESH_INTERVAL"), 60.0)
    scan_limit = max(50, min(20000, env_int_fn(provider_env_name("claude", "BIND_SCAN_LIMIT"), 400)))

    with registry._lock:
        snapshot = [(key, entry.work_dir) for key, entry in registry._sessions.items() if entry.valid]

    for key, work_dir in snapshot:
        try:
            registry._check_one(key, work_dir, now=now, refresh_interval_s=refresh_interval_s, scan_limit=scan_limit)
        except Exception:
            continue

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


def check_one(
    registry,
    key: str,
    work_dir: Path,
    *,
    now: float,
    refresh_interval_s: float,
    scan_limit: int,
    find_project_session_file_fn: Callable[[Path, str], Optional[Path]],
    resolve_project_config_dir_fn: Callable[[Path], Path],
    load_project_session_fn: Callable[[Path], object | None],
    refresh_claude_log_binding_fn,
    write_log_fn: Callable[[str], None],
) -> None:
    session_file = find_project_session_file_fn(work_dir, ".claude-session") or (
        resolve_project_config_dir_fn(work_dir) / ".claude-session"
    )
    try:
        exists = session_file.exists()
    except Exception:
        exists = False

    if not exists:
        with registry._lock:
            entry = registry._sessions.get(key)
            if entry and entry.valid:
                write_log_fn(f"[WARN] Session file deleted: {work_dir}")
                entry.valid = False
                entry.last_check = now
        return

    try:
        current_mtime = session_file.stat().st_mtime
    except Exception:
        current_mtime = 0.0

    session = None
    file_changed = False

    with registry._lock:
        entry = registry._sessions.get(key)
        if not entry or not entry.valid:
            return
        file_changed = bool((entry.session_file != session_file) or (entry.file_mtime != current_mtime))
        if file_changed or (entry.session is None):
            session = load_project_session_fn(work_dir)
            entry.session = session
            entry.session_file = session_file
            entry.file_mtime = current_mtime
        else:
            session = entry.session

    if not session:
        with registry._lock:
            entry2 = registry._sessions.get(key)
            if entry2 and entry2.valid:
                entry2.valid = False
                entry2.last_check = now
        return

    try:
        ok, _ = session.ensure_pane()
    except Exception:
        ok = False
    if not ok:
        with registry._lock:
            entry2 = registry._sessions.get(key)
            if entry2 and entry2.valid:
                write_log_fn(f"[WARN] Session pane invalid: {work_dir}")
                entry2.valid = False
                entry2.last_check = now
        return

    with registry._lock:
        entry3 = registry._sessions.get(key)
        if not entry3 or not entry3.valid:
            return
        due = now >= (entry3.next_bind_refresh or 0.0)
        if not due and not file_changed:
            entry3.last_check = now
            return
        backoff = entry3.bind_backoff_s or refresh_interval_s

    force_scan = bool(file_changed)
    try:
        updated = bool(
            refresh_claude_log_binding_fn(
                session,
                root=registry._claude_root,
                scan_limit=scan_limit,
                force_scan=force_scan,
            )
        )
    except Exception:
        updated = False

    with registry._lock:
        entry4 = registry._sessions.get(key)
        if not entry4 or not entry4.valid:
            return
        if updated:
            entry4.bind_backoff_s = refresh_interval_s
        else:
            entry4.bind_backoff_s = min(600.0, max(refresh_interval_s, backoff * 2.0))
        entry4.next_bind_refresh = now + entry4.bind_backoff_s
        try:
            entry4.file_mtime = session_file.stat().st_mtime
        except Exception:
            pass
        entry4.last_check = now


__all__ = [
    "check_all_sessions",
    "check_one",
    "monitor_loop",
    "start_monitor",
    "stop_monitor",
]
