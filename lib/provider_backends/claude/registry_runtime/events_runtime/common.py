from __future__ import annotations

from pathlib import Path
from typing import Any

from ..session_updates import update_session_file_direct


def safe_update_binding(session, *, session_path: Path, session_id: str) -> bool:
    if session is None:
        return False
    try:
        session.update_claude_binding(session_path=session_path, session_id=session_id)
        return True
    except Exception:
        return False


def update_session_file(registry: Any, work_dir: Path, *, session_path: Path, session_id: str) -> None:
    session_file = registry._find_claude_session_file(work_dir)
    if session_file:
        update_session_file_direct(session_file, session_path, session_id)


def load_session_for_entry(registry: Any, entry) -> Any | None:
    if entry is None:
        return None
    if entry.session is not None:
        return entry.session
    session = registry._load_claude_session(entry.work_dir)
    if session is None:
        return None
    try:
        entry.session = session
        entry.session_file = session.session_file
    except Exception:
        pass
    return session


def watcher_entries(registry: Any, project_key: str) -> list[tuple[str, Any]]:
    with registry._lock:
        watcher_entry = registry._watchers.get(project_key)
        if not watcher_entry:
            return []
        keys = list(watcher_entry.keys)
        return [(key, registry._sessions.get(key)) for key in keys]


__all__ = [
    "load_session_for_entry",
    "safe_update_binding",
    "update_session_file",
    "watcher_entries",
]
