from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...registry_support.pathing import candidate_project_paths, normalize_project_path

from .membership import project_dir, session_belongs_to_current_project


def parse_sessions_index(reader) -> Path | None:
    if not reader._use_sessions_index:
        return None
    current_project_dir = project_dir(reader)
    index_path = current_project_dir / "sessions-index.json"
    if not index_path.exists():
        return None
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return None
    candidates = set(candidate_project_paths(reader.work_dir))
    best_path: Path | None = None
    best_mtime = -1
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("isSidechain") is True:
            continue
        project_path = entry.get("projectPath")
        if isinstance(project_path, str) and project_path.strip():
            normalized = normalize_project_path(project_path)
            if candidates and normalized and normalized not in candidates:
                continue
        elif candidates:
            continue
        full_path = entry.get("fullPath")
        if not isinstance(full_path, str) or not full_path.strip():
            continue
        try:
            session_path = Path(full_path).expanduser()
        except Exception:
            continue
        if not session_path.is_absolute():
            session_path = (current_project_dir / session_path).expanduser()
        if not session_path.exists():
            continue
        if not session_belongs_to_current_project(reader, session_path):
            continue
        mtime = entry_mtime(entry, session_path)
        if mtime is None:
            continue
        if mtime > best_mtime:
            best_mtime = mtime
            best_path = session_path
    return best_path


def entry_mtime(entry: dict[str, Any], session_path: Path) -> int | None:
    mtime_raw = entry.get("fileMtime")
    if isinstance(mtime_raw, (int, float)):
        return int(mtime_raw)
    if isinstance(mtime_raw, str) and mtime_raw.strip().isdigit():
        try:
            return int(mtime_raw.strip())
        except Exception:
            return None
    try:
        return int(session_path.stat().st_mtime * 1000)
    except OSError:
        return None


__all__ = ["parse_sessions_index"]
