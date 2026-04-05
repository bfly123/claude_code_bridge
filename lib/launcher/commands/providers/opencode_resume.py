from __future__ import annotations

import json
from pathlib import Path


def opencode_resume_allowed(factory) -> bool:
    try:
        from provider_backends.opencode.comm import OPENCODE_STORAGE_ROOT
    except Exception:
        return False

    root = Path(OPENCODE_STORAGE_ROOT)
    sessions_root = root / "session"
    if not sessions_root.exists():
        return False

    target_dir = factory.normalize_path_for_match_fn(str(factory.project_root))
    if not target_dir:
        return False

    def _load_json(path: Path) -> dict:
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _session_dir_has_match(dir_path: Path) -> bool:
        if not dir_path.exists():
            return False
        try:
            session_files = list(dir_path.glob("ses_*.json"))
        except Exception:
            session_files = []
        for path in session_files:
            if not path.is_file():
                continue
            payload = _load_json(path)
            directory = payload.get("directory")
            if not isinstance(directory, str) or not directory.strip():
                continue
            if factory.normalize_path_for_match_fn(directory) == target_dir:
                return True
        return False

    projects_root = root / "project"
    candidate_ids: list[str] = []
    if projects_root.exists():
        try:
            project_files = list(projects_root.glob("*.json"))
        except Exception:
            project_files = []
        for path in project_files:
            if not path.is_file():
                continue
            payload = _load_json(path)
            worktree = payload.get("worktree")
            if not isinstance(worktree, str) or not worktree.strip():
                continue
            if factory.normalize_path_for_match_fn(worktree) != target_dir:
                continue
            project_id = payload.get("id") if isinstance(payload.get("id"), str) and payload.get("id") else path.stem
            if project_id:
                candidate_ids.append(project_id)

    for project_id in candidate_ids:
        if _session_dir_has_match(sessions_root / project_id):
            return True
    if _session_dir_has_match(sessions_root / "global"):
        return True
    try:
        project_dirs = list(sessions_root.iterdir())
    except Exception:
        project_dirs = []
    for project_dir in project_dirs:
        if project_dir.is_dir() and _session_dir_has_match(project_dir):
            return True
    return False
