from __future__ import annotations

import os
from pathlib import Path

from .indexing import parse_sessions_index
from .membership import project_dir, session_belongs_to_current_project, session_is_sidechain


def scan_latest_session_any_project(reader) -> Path | None:
    if not reader.root.exists():
        return None
    try:
        sessions = sorted(
            (path for path in reader.root.glob("*/*.jsonl") if path.is_file() and not path.name.startswith(".")),
            key=lambda path: path.stat().st_mtime,
        )
    except OSError:
        return None
    return sessions[-1] if sessions else None


def scan_latest_session(reader) -> Path | None:
    current_project_dir = project_dir(reader)
    if not current_project_dir.exists():
        return None
    try:
        sessions = sorted(
            (path for path in current_project_dir.glob("*.jsonl") if path.is_file() and not path.name.startswith(".")),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return None
    if not sessions:
        return None
    first_unknown: Path | None = None
    first_any = sessions[0]
    for session in sessions:
        sidechain = session_is_sidechain(session)
        if sidechain is False:
            return session
        if sidechain is None and first_unknown is None:
            first_unknown = session
    return first_unknown or first_any


def latest_session(reader) -> Path | None:
    preferred = reader._preferred_session
    if preferred and not session_belongs_to_current_project(reader, preferred):
        reader._preferred_session = None
        preferred = None
    index_session = parse_sessions_index(reader)
    scanned = scan_latest_session(reader) if index_session is None else None
    if preferred and preferred.exists():
        candidate = newer_candidate(preferred, index_session, scanned)
        if candidate is not None:
            reader._preferred_session = candidate
            return candidate
        return preferred
    if index_session:
        reader._preferred_session = index_session
        return index_session
    if scanned:
        reader._preferred_session = scanned
        return scanned
    if os.environ.get("CLAUDE_ALLOW_ANY_PROJECT_SCAN") in ("1", "true", "yes"):
        any_latest = scan_latest_session_any_project(reader)
        if any_latest:
            reader._preferred_session = any_latest
            return any_latest
    return None


def newer_candidate(preferred: Path, index_session: Path | None, scanned: Path | None) -> Path | None:
    for candidate in (index_session, scanned):
        if not candidate or not candidate.exists():
            continue
        try:
            if candidate.stat().st_mtime > preferred.stat().st_mtime:
                return candidate
        except OSError:
            continue
    return None


__all__ = [
    "latest_session",
    "scan_latest_session",
    "scan_latest_session_any_project",
]
