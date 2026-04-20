from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional


def get_session(
    registry,
    work_dir: Path,
    *,
    find_session_file_fn: Callable[[Path], Optional[Path]],
    write_log_fn: Callable[[str], None],
    load_and_cache_fn: Callable[[Path], object | None],
):
    key = str(work_dir)
    should_reload = False
    with registry._lock:
        entry = registry._sessions.get(key)
        if entry:
            session_file = _session_file(
                work_dir,
                entry=entry,
                find_session_file_fn=find_session_file_fn,
            )
            should_reload = _should_reload(entry, session_file, work_dir=work_dir, write_log_fn=write_log_fn)
            if not should_reload and entry.valid:
                return entry.session
        else:
            should_reload = True
    if should_reload:
        entry = load_and_cache_fn(work_dir)
        if entry:
            return entry.session
    return None


def _session_file(
    work_dir: Path,
    *,
    entry,
    find_session_file_fn: Callable[[Path], Optional[Path]],
) -> Path | None:
    return (
        entry.session_file
        or find_session_file_fn(work_dir)
    )


def _should_reload(entry, session_file: Path | None, *, work_dir: Path, write_log_fn: Callable[[str], None]) -> bool:
    if not session_file or not session_file.exists():
        return False
    try:
        current_mtime = session_file.stat().st_mtime
    except Exception:
        return False
    if (not entry.session_file) or (session_file != entry.session_file) or (current_mtime != entry.file_mtime):
        write_log_fn(f'[INFO] Session file changed, reloading: {work_dir}')
        return True
    return False


__all__ = ['get_session']
