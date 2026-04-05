from __future__ import annotations

from pathlib import Path

from provider_backends.claude.session import ClaudeProjectSession

from .discovery import extract_session_id_from_start_cmd, find_log_for_session_id, scan_latest_log_for_work_dir
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
    current_log_str = session.claude_session_path
    current_log = Path(current_log_str).expanduser() if current_log_str else None

    start_cmd = str(session.data.get("claude_start_cmd") or session.data.get("start_cmd") or "").strip()
    intended_sid = extract_session_id_from_start_cmd(start_cmd)
    intended_log: Path | None = None
    if intended_sid:
        intended_log = find_log_for_session_id(intended_sid, root=root)
        if intended_log and intended_log.exists():
            if should_overwrite_binding(current_log, intended_log) or session.claude_session_id != intended_sid:
                session.update_claude_binding(session_path=intended_log, session_id=intended_sid)
                return True
            return False

    index_session = parse_sessions_index(Path(session.work_dir), root=root)
    if index_session and index_session.exists():
        index_sid = index_session.stem
        if should_overwrite_binding(current_log, index_session) or session.claude_session_id != index_sid:
            session.update_claude_binding(session_path=index_session, session_id=index_sid)
            return True
        if not force_scan:
            return False

    need_scan = bool(force_scan or (not intended_log and not index_session))
    if not need_scan:
        return False

    candidate_log, candidate_sid = scan_latest_log_for_work_dir(Path(session.work_dir), root=root, scan_limit=scan_limit)
    if not candidate_log or not candidate_log.exists():
        return False

    if should_overwrite_binding(current_log, candidate_log) or (candidate_sid and candidate_sid != session.claude_session_id):
        session.update_claude_binding(session_path=candidate_log, session_id=candidate_sid)
        return True
    return False


__all__ = [
    "refresh_claude_log_binding",
    "should_overwrite_binding",
]
