from __future__ import annotations

import json
from pathlib import Path

from ..pathing import candidate_project_paths, normalize_project_path, project_key_for_path


def parse_sessions_index(work_dir: Path, *, root: Path) -> Path | None:
    candidates = set(candidate_project_paths(work_dir))

    project_key = project_key_for_path(work_dir)
    project_dir = root / project_key
    index_path = project_dir / "sessions-index.json"
    if not index_path.exists():
        try:
            resolved = work_dir.resolve()
        except Exception:
            resolved = work_dir
        if resolved != work_dir:
            alt_key = project_key_for_path(resolved)
            index_path = root / alt_key / "sessions-index.json"
            project_dir = root / alt_key
    if not index_path.exists():
        return None

    try:
        payload = json.loads(index_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None

    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return None

    best_path: Path | None = None
    best_mtime = -1
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("isSidechain") is True:
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
            session_path = (project_dir / session_path).expanduser()
        if not session_path.exists():
            continue
        mtime = _entry_mtime(entry, session_path)
        if mtime is None:
            continue
        if mtime > best_mtime:
            best_mtime = mtime
            best_path = session_path
    return best_path


def _entry_mtime(entry: dict, session_path: Path) -> int | None:
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
