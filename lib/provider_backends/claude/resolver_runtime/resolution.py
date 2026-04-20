from __future__ import annotations

from pathlib import Path

from provider_core.session_binding_runtime import find_bound_session_file

from ..home_layout import claude_layout_from_session_data
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
    _backfill_layout_fields(data)
    return select_resolution(data, session_file, None, "session_file")


def _backfill_layout_fields(data: dict) -> None:
    layout = claude_layout_from_session_data(data)
    if layout is None:
        return
    data.setdefault("claude_home", str(layout.home_root))
    data.setdefault("claude_projects_root", str(layout.projects_root))
    data.setdefault("claude_session_env_root", str(layout.session_env_root))


__all__ = ["resolve_claude_session"]
