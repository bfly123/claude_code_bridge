from __future__ import annotations

import os
import re
from pathlib import Path

from .models import CLAUDE_PROJECTS_ROOT


def project_key_for_path(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def candidate_project_dirs(root: Path, work_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    env_pwd = os.environ.get("PWD")
    if env_pwd:
        try:
            candidates.append(Path(env_pwd))
        except Exception:
            pass
    candidates.append(work_dir)
    try:
        candidates.append(work_dir.resolve())
    except Exception:
        pass

    out: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = project_key_for_path(candidate)
        if key in seen:
            continue
        seen.add(key)
        out.append(root / key)
    return out


def session_path_from_id(session_id: str, work_dir: Path) -> Path | None:
    sid = str(session_id or "").strip()
    if not sid:
        return None
    for project_dir in candidate_project_dirs(CLAUDE_PROJECTS_ROOT, work_dir):
        candidate = project_dir / f"{sid}.jsonl"
        if candidate.exists():
            return candidate
    return None


def normalize_session_binding(data: dict, work_dir: Path) -> None:
    if not isinstance(data, dict):
        return
    sid = str(data.get("claude_session_id") or "").strip()
    path_value = str(data.get("claude_session_path") or "").strip()
    path: Path | None = None
    if path_value:
        try:
            path = Path(path_value).expanduser()
        except Exception:
            path = None
    if path and path.exists():
        if sid and path.stem != sid:
            candidate = session_path_from_id(sid, work_dir)
            if candidate and candidate.exists():
                data["claude_session_path"] = str(candidate)
            else:
                data["claude_session_id"] = path.stem
        elif not sid:
            data["claude_session_id"] = path.stem
        return
    if sid:
        candidate = session_path_from_id(sid, work_dir)
        if candidate and candidate.exists():
            data["claude_session_path"] = str(candidate)


__all__ = [
    "candidate_project_dirs",
    "normalize_session_binding",
    "project_key_for_path",
    "session_path_from_id",
]
