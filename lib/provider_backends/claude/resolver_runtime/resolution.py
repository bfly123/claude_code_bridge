from __future__ import annotations

import os
from pathlib import Path

from provider_sessions.files import find_project_session_file

from .json_io import read_json
from .models import ClaudeSessionResolution
from .pathing import normalize_session_binding


def select_resolution(
    data: dict,
    session_file: Path | None,
    record: dict | None,
    source: str,
) -> ClaudeSessionResolution:
    return ClaudeSessionResolution(
        data=data,
        session_file=session_file,
        registry=record,
        source=source,
    )


def _explicit_session_file() -> Path | None:
    raw = (os.environ.get("CCB_SESSION_FILE") or "").strip()
    if not raw:
        return None
    try:
        session_file = Path(os.path.expanduser(raw))
    except Exception:
        return None
    if session_file.name != ".claude-session":
        return None
    return session_file if session_file.is_file() else None


def _session_work_dir(session_file: Path, fallback_work_dir: Path) -> Path:
    try:
        resolved = session_file.expanduser().resolve()
    except Exception:
        resolved = session_file.expanduser().absolute()
    if resolved.parent.name == ".ccb":
        return resolved.parent.parent
    return fallback_work_dir


def resolve_claude_session(work_dir: Path) -> ClaudeSessionResolution | None:
    session_file = _explicit_session_file() or find_project_session_file(work_dir, ".claude-session")
    if not session_file:
        return None
    data = read_json(session_file)
    if not data:
        return None
    session_work_dir = _session_work_dir(session_file, work_dir)
    data.setdefault("work_dir", str(session_work_dir))
    normalize_session_binding(data, session_work_dir)
    return select_resolution(data, session_file, None, "session_file")


__all__ = ["resolve_claude_session"]
