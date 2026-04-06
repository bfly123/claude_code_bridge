from __future__ import annotations

from pathlib import Path

from provider_backends.claude.session import ClaudeProjectSession

from .discovery import (
    extract_session_id_from_start_cmd,
    find_log_for_session_id,
    scan_latest_log_for_work_dir,
)
from .indexing import parse_sessions_index


def should_overwrite_binding(current: Path | None, candidate: Path) -> bool:
    if not current or not current.exists():
        return True
    try:
        return candidate.stat().st_mtime > current.stat().st_mtime
    except OSError:
        return True


def refresh_claude_log_binding(
    session: ClaudeProjectSession,
    *,
    root: Path,
    scan_limit: int,
    force_scan: bool,
) -> bool:
    current_log = _current_log_path(session)
    intended_log, intended_sid = _intended_log_binding(session, root=root)
    if _binding_exists(intended_log):
        return _refresh_from_candidate(
            session,
            current_log=current_log,
            candidate_log=intended_log,
            candidate_sid=intended_sid,
        )

    index_log = _indexed_log_binding(session, root=root)
    if _binding_exists(index_log):
        updated = _refresh_from_candidate(
            session,
            current_log=current_log,
            candidate_log=index_log,
            candidate_sid=index_log.stem,
        )
        if updated or not force_scan:
            return updated

    if not _need_scan(force_scan=force_scan, intended_log=intended_log, index_log=index_log):
        return False

    candidate_log, candidate_sid = _scanned_log_binding(
        session,
        root=root,
        scan_limit=scan_limit,
    )
    if not _binding_exists(candidate_log):
        return False
    return _refresh_from_candidate(
        session,
        current_log=current_log,
        candidate_log=candidate_log,
        candidate_sid=candidate_sid,
    )


def _current_log_path(session: ClaudeProjectSession) -> Path | None:
    current_log_str = session.claude_session_path
    if not current_log_str:
        return None
    return Path(current_log_str).expanduser()


def _start_cmd(session: ClaudeProjectSession) -> str:
    raw = session.data.get("claude_start_cmd") or session.data.get("start_cmd") or ""
    return str(raw).strip()


def _intended_log_binding(
    session: ClaudeProjectSession,
    *,
    root: Path,
) -> tuple[Path | None, str | None]:
    intended_sid = extract_session_id_from_start_cmd(_start_cmd(session))
    if not intended_sid:
        return None, None
    return find_log_for_session_id(intended_sid, root=root), intended_sid


def _indexed_log_binding(session: ClaudeProjectSession, *, root: Path) -> Path | None:
    return parse_sessions_index(Path(session.work_dir), root=root)


def _scanned_log_binding(
    session: ClaudeProjectSession,
    *,
    root: Path,
    scan_limit: int,
) -> tuple[Path | None, str | None]:
    return scan_latest_log_for_work_dir(
        Path(session.work_dir),
        root=root,
        scan_limit=scan_limit,
    )


def _binding_exists(candidate: Path | None) -> bool:
    return candidate is not None and candidate.exists()


def _need_scan(*, force_scan: bool, intended_log: Path | None, index_log: Path | None) -> bool:
    return bool(force_scan or (not intended_log and not index_log))


def _refresh_from_candidate(
    session: ClaudeProjectSession,
    *,
    current_log: Path | None,
    candidate_log: Path,
    candidate_sid: str | None,
) -> bool:
    if not _should_update_session_binding(
        session,
        current_log=current_log,
        candidate_log=candidate_log,
        candidate_sid=candidate_sid,
    ):
        return False
    session.update_claude_binding(session_path=candidate_log, session_id=candidate_sid)
    return True


def _should_update_session_binding(
    session: ClaudeProjectSession,
    *,
    current_log: Path | None,
    candidate_log: Path,
    candidate_sid: str | None,
) -> bool:
    if should_overwrite_binding(current_log, candidate_log):
        return True
    return bool(candidate_sid and candidate_sid != session.claude_session_id)


__all__ = [
    "refresh_claude_log_binding",
    "should_overwrite_binding",
]
