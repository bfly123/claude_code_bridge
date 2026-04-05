from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional


def get_session(
    registry,
    work_dir: Path,
    *,
    find_project_session_file_fn: Callable[[Path, str], Optional[Path]],
    resolve_project_config_dir_fn: Callable[[Path], Path],
    write_log_fn: Callable[[str], None],
    load_and_cache_fn: Callable[[Path], object | None],
):
    key = str(work_dir)
    should_reload = False

    with registry._lock:
        entry = registry._sessions.get(key)
        if entry:
            session_file = (
                entry.session_file
                or find_project_session_file_fn(work_dir, ".claude-session")
                or (resolve_project_config_dir_fn(work_dir) / ".claude-session")
            )
            if session_file.exists():
                try:
                    current_mtime = session_file.stat().st_mtime
                    if (not entry.session_file) or (session_file != entry.session_file) or (current_mtime != entry.file_mtime):
                        write_log_fn(f"[INFO] Session file changed, reloading: {work_dir}")
                        should_reload = True
                    elif entry.valid:
                        return entry.session
                except Exception:
                    if entry.valid:
                        return entry.session
            elif entry.valid:
                return entry.session
        else:
            should_reload = True

    if should_reload:
        entry = load_and_cache_fn(work_dir)
        if entry:
            return entry.session

    return None


def register_session(
    registry,
    work_dir: Path,
    session,
    *,
    session_entry_cls,
    ensure_watchers_for_work_dir_fn: Callable[[Path, str], None],
) -> None:
    key = str(work_dir)
    session_file = session.session_file
    mtime = 0.0
    if session_file and session_file.exists():
        try:
            mtime = session_file.stat().st_mtime
        except Exception:
            pass

    with registry._lock:
        entry = session_entry_cls(
            work_dir=work_dir,
            session=session,
            session_file=session_file,
            file_mtime=mtime,
            last_check=time.time(),
            valid=True,
            next_bind_refresh=0.0,
            bind_backoff_s=0.0,
        )
        registry._sessions[key] = entry
    ensure_watchers_for_work_dir_fn(work_dir, key)


def load_and_cache(
    registry,
    work_dir: Path,
    *,
    session_entry_cls,
    load_project_session_fn: Callable[[Path], object | None],
    find_project_session_file_fn: Callable[[Path, str], Optional[Path]],
    resolve_project_config_dir_fn: Callable[[Path], Path],
):
    session = load_project_session_fn(work_dir)
    session_file = (
        session.session_file
        if session
        else (
            find_project_session_file_fn(work_dir, ".claude-session")
            or (resolve_project_config_dir_fn(work_dir) / ".claude-session")
        )
    )
    mtime = 0.0
    if session_file.exists():
        try:
            mtime = session_file.stat().st_mtime
        except Exception:
            pass

    valid = False
    if session is not None:
        try:
            ok, _ = session.ensure_pane()
            valid = bool(ok)
        except Exception:
            valid = False

    entry = session_entry_cls(
        work_dir=work_dir,
        session=session,
        session_file=session_file if session_file.exists() else None,
        file_mtime=mtime,
        last_check=time.time(),
        valid=valid,
        next_bind_refresh=0.0,
        bind_backoff_s=0.0,
    )
    with registry._lock:
        registry._sessions[str(work_dir)] = entry
    return entry if entry.valid else None


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
            write_log_fn(f"[INFO] Session invalidated: {work_dir}")
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
            write_log_fn(f"[INFO] Session removed: {work_dir}")
    release_watchers_for_work_dir_fn(work_dir, key)


__all__ = [
    "get_session",
    "invalidate",
    "load_and_cache",
    "register_session",
    "remove",
]
