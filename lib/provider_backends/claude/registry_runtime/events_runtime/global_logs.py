from __future__ import annotations

from pathlib import Path
from typing import Any

from ..session_updates import read_log_meta_with_retry
from .common import safe_update_binding, update_session_file
from .sessions_index import handle_sessions_index


def handle_new_log_file_global(registry: Any, path: Path) -> None:
    if path.name == "sessions-index.json":
        handle_sessions_index(registry, str(path.parent), path)
        return
    if not path.exists():
        return

    work_dir, session_id = _discover_log_binding(path)
    if work_dir is None or session_id is None:
        return

    update_session_file(registry, work_dir, session_path=path, session_id=session_id)
    key = str(work_dir)
    with registry._lock:
        entry = registry._sessions.get(key)
        session = entry.session if entry else None
    safe_update_binding(session, session_path=path, session_id=session_id)


def _discover_log_binding(path: Path) -> tuple[Path | None, str | None]:
    cwd, sid, is_sidechain = read_log_meta_with_retry(path)
    if is_sidechain is True or not cwd:
        return None, None
    session_id = sid or path.stem
    if not session_id:
        return None, None
    return Path(cwd), session_id


__all__ = ["handle_new_log_file_global"]
