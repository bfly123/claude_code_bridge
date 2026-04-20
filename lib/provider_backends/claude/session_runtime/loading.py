from __future__ import annotations

from pathlib import Path

from project.identity import compute_ccb_project_id, compute_worktree_scope_id
from provider_core.session_binding_runtime import find_bound_session_file

from ..resolver import resolve_claude_session
from .normalization import normalize_session_data
from .model import ClaudeProjectSession
from .pathing import ensure_work_dir_fields, find_project_session_file, read_json


def _backfill_project_id(data: dict, *, fallback_work_dir: Path) -> None:
    if data.get("ccb_project_id"):
        return
    try:
        data["ccb_project_id"] = compute_ccb_project_id(Path(data.get("work_dir") or fallback_work_dir))
    except Exception:
        pass


def _build_session(
    *,
    session_file: Path,
    data: dict,
    fallback_work_dir: Path,
) -> ClaudeProjectSession:
    data.setdefault("work_dir", str(fallback_work_dir))
    _backfill_project_id(data, fallback_work_dir=fallback_work_dir)
    ensure_work_dir_fields(data, session_file=session_file, fallback_work_dir=fallback_work_dir)
    migrated = normalize_session_data(data)
    session = ClaudeProjectSession(session_file=session_file, data=data)
    if migrated:
        session._write_back()
    return session

def _load_session_from_file(session_file: Path, *, fallback_work_dir: Path) -> ClaudeProjectSession | None:
    data = read_json(session_file)
    if not data:
        return None
    return _build_session(session_file=session_file, data=data, fallback_work_dir=fallback_work_dir)


def _resolved_session_file(work_dir: Path, *, session_file: Path | None) -> Path | None:
    if session_file is not None:
        return session_file
    return find_bound_session_file(
        provider="claude",
        base_filename=".claude-session",
        work_dir=work_dir,
    )


def _load_resolved_session(work_dir: Path) -> ClaudeProjectSession | None:
    resolution = resolve_claude_session(work_dir)
    if not resolution:
        return None
    data = dict(resolution.data or {})
    if not data:
        return None
    data.setdefault("work_dir", str(work_dir))
    _backfill_project_id(data, fallback_work_dir=work_dir)
    session_file = _resolved_session_file(work_dir, session_file=resolution.session_file)
    if session_file is None:
        return None
    return _build_session(session_file=session_file, data=data, fallback_work_dir=work_dir)


def load_project_session(work_dir: Path, instance: str | None = None) -> ClaudeProjectSession | None:
    # Named agents must bind only to their own instance-scoped session file.
    # Falling back to the primary session incorrectly aliases agent runtimes.
    if instance:
        session_file = find_project_session_file(work_dir, instance)
        if session_file is None:
            return None
        return _load_session_from_file(session_file, fallback_work_dir=work_dir)

    session_file = find_project_session_file(work_dir)
    if session_file is not None:
        session = _load_session_from_file(session_file, fallback_work_dir=work_dir)
        if session is not None:
            return session

    # Fallback: support explicit CCB_SESSION_FILE when the caller is outside the project tree.
    return _load_resolved_session(work_dir)


def compute_session_key(session: ClaudeProjectSession, instance: str | None = None) -> str:
    project_id = str(session.data.get("ccb_project_id") or "").strip()
    if not project_id:
        try:
            project_id = compute_ccb_project_id(Path(session.work_dir))
        except Exception:
            project_id = ""
    worktree_scope = ""
    try:
        worktree_scope = compute_worktree_scope_id(Path(session.work_dir))
    except Exception:
        worktree_scope = ""
    prefix = "claude" if not instance else f"claude:{instance}"
    if project_id and worktree_scope:
        return f"{prefix}:{project_id}:{worktree_scope}"
    if project_id:
        return f"{prefix}:{project_id}"
    if worktree_scope:
        return f"{prefix}:unknown:{worktree_scope}"
    return f"{prefix}:unknown"


__all__ = [
    "compute_session_key",
    "find_project_session_file",
    "load_project_session",
]
