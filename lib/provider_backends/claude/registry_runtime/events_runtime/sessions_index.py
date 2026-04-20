from __future__ import annotations

from pathlib import Path
from typing import Any

from provider_backends.claude.registry_support.logs import parse_sessions_index

from .common import load_session_for_entry, safe_update_binding, update_session_file, watcher_entries


def handle_sessions_index(registry: Any, project_key: str, index_path: Path) -> None:
    if not index_path.exists():
        return

    for _key, entry in watcher_entries(registry, project_key):
        if not entry:
            continue
        work_dir = entry.work_dir
        session_path = parse_sessions_index(work_dir, root=registry._claude_root)
        if not session_path or not session_path.exists():
            continue
        session_id = session_path.stem
        update_session_file(registry, work_dir, session_path=session_path, session_id=session_id)
        session = load_session_for_entry(registry, entry)
        safe_update_binding(session, session_path=session_path, session_id=session_id)


__all__ = ["handle_sessions_index"]
