from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

from memory.types import SessionNotFoundError


def resolve_session(parser, work_dir: Path, session_path: Optional[Path] = None) -> Path:
    if session_path and session_path.exists():
        return session_path

    index_session = resolve_from_index(parser, work_dir)
    if index_session:
        return index_session

    project_session = scan_project_dir(parser, work_dir)
    if project_session:
        return project_session

    if os.environ.get("CLAUDE_ALLOW_ANY_PROJECT_SCAN") == "1":
        any_session = scan_all_projects(parser)
        if any_session:
            return any_session

    raise SessionNotFoundError(f"No session found for {work_dir}")


def resolve_from_index(parser, work_dir: Path) -> Optional[Path]:
    index_path = parser.root / "sessions-index.json"
    if not index_path.exists():
        return None

    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        sessions = data.get("sessions", [])
        if not sessions:
            return None

        work_dir_str = str(work_dir.resolve())
        candidates = []
        for session in sessions:
            if session.get("isSidechain"):
                continue
            project_path = session.get("projectPath", "")
            if project_path and work_dir_str.startswith(project_path):
                candidates.append(session)

        if not candidates:
            candidates = [session for session in sessions if not session.get("isSidechain")]
        if not candidates:
            return None

        candidates.sort(key=lambda item: item.get("lastModified", 0), reverse=True)
        session_id = candidates[0].get("sessionId")
        if not session_id:
            return None
        return find_session_file(parser, session_id, work_dir)
    except Exception:
        return None


def find_session_file(parser, session_id: str, work_dir: Path) -> Optional[Path]:
    project_dir = get_project_dir(parser, work_dir)
    if project_dir:
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate

    for project_dir in parser.root.iterdir():
        if not project_dir.is_dir():
            continue
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate
    return None


def get_project_dir(parser, work_dir: Path) -> Optional[Path]:
    key = re.sub(r"[^A-Za-z0-9]", "-", str(work_dir.resolve()))
    project_dir = parser.root / key
    if project_dir.exists():
        return project_dir
    return None


def scan_project_dir(parser, work_dir: Path) -> Optional[Path]:
    project_dir = get_project_dir(parser, work_dir)
    if not project_dir or not project_dir.exists():
        return None

    jsonl_files = list(project_dir.glob("*.jsonl"))
    if not jsonl_files:
        return None
    jsonl_files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return jsonl_files[0]


def scan_all_projects(parser) -> Optional[Path]:
    if not parser.root.exists():
        return None

    best: Optional[Path] = None
    best_mtime = 0.0
    for project_dir in parser.root.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            try:
                mtime = jsonl_file.stat().st_mtime
            except Exception:
                continue
            if mtime > best_mtime:
                best_mtime = mtime
                best = jsonl_file
    return best


__all__ = [
    "find_session_file",
    "get_project_dir",
    "resolve_from_index",
    "resolve_session",
    "scan_all_projects",
    "scan_project_dir",
]
