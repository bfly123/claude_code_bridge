from __future__ import annotations

from pathlib import Path

from ..membership import project_dir, session_is_sidechain


def scan_latest_session_any_project(reader) -> Path | None:
    if not reader.root.exists():
        return None
    try:
        sessions = sorted(
            (path for path in reader.root.glob('*/*.jsonl') if path.is_file() and not path.name.startswith('.')),
            key=_session_mtime,
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
            (path for path in current_project_dir.glob('*.jsonl') if path.is_file() and not path.name.startswith('.')),
            key=_session_mtime,
            reverse=True,
        )
    except OSError:
        return None
    if not sessions:
        return None
    return _best_project_session(sessions)


def _best_project_session(sessions: list[Path]) -> Path | None:
    first_unknown: Path | None = None
    first_any = sessions[0]
    for session in sessions:
        sidechain = session_is_sidechain(session)
        if sidechain is False:
            return session
        if sidechain is None and first_unknown is None:
            first_unknown = session
    return first_unknown or first_any


def _session_mtime(path: Path) -> float:
    return path.stat().st_mtime


__all__ = ['scan_latest_session', 'scan_latest_session_any_project']
