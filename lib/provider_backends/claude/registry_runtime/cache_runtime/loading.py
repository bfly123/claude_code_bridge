from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional


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
    entry = session_entry_cls(
        work_dir=work_dir,
        session=session,
        session_file=session_file,
        file_mtime=_file_mtime(session_file),
        last_check=time.time(),
        valid=True,
        next_bind_refresh=0.0,
        bind_backoff_s=0.0,
    )
    with registry._lock:
        registry._sessions[key] = entry
    ensure_watchers_for_work_dir_fn(work_dir, key)


def load_and_cache(
    registry,
    work_dir: Path,
    *,
    session_entry_cls,
    load_session_fn: Callable[[Path], object | None],
    find_session_file_fn: Callable[[Path], Optional[Path]],
):
    session = load_session_fn(work_dir)
    session_file = _session_file(
        work_dir,
        session=session,
        find_session_file_fn=find_session_file_fn,
    )
    valid = _session_valid(session)
    entry = session_entry_cls(
        work_dir=work_dir,
        session=session,
        session_file=session_file if session_file.exists() else None,
        file_mtime=_file_mtime(session_file),
        last_check=time.time(),
        valid=valid,
        next_bind_refresh=0.0,
        bind_backoff_s=0.0,
    )
    with registry._lock:
        registry._sessions[str(work_dir)] = entry
    return entry if entry.valid else None


def _session_file(
    work_dir: Path,
    *,
    session,
    find_session_file_fn: Callable[[Path], Optional[Path]],
) -> Path | None:
    if session and session.session_file:
        return session.session_file
    return find_session_file_fn(work_dir)


def _session_valid(session) -> bool:
    if session is None:
        return False
    try:
        ok, _ = session.ensure_pane()
        return bool(ok)
    except Exception:
        return False


def _file_mtime(path: Path | None) -> float:
    if path and path.exists():
        try:
            return path.stat().st_mtime
        except Exception:
            return 0.0
    return 0.0


__all__ = ['load_and_cache', 'register_session']
