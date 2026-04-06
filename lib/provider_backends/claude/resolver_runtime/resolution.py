from __future__ import annotations

from pathlib import Path

from provider_core.session_binding_runtime import find_bound_session_file

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


def _session_work_dir(session_file: Path, fallback_work_dir: Path) -> Path:
    try:
        resolved = session_file.expanduser().resolve()
    except Exception:
        resolved = session_file.expanduser().absolute()
    if resolved.parent.name == ".ccb":
        return resolved.parent.parent
    return fallback_work_dir


def resolve_claude_session(work_dir: Path) -> ClaudeSessionResolution | None:
    session_file = find_bound_session_file(
        provider="claude",
        base_filename=".claude-session",
        work_dir=work_dir,
    )
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
