from __future__ import annotations

from pathlib import Path

from ...debug import debug_log_reader
from ...pathing import extract_cwd_from_log


def candidate_logs(reader):
    if not reader.root.exists():
        return
    try:
        for path in reader.root.glob("**/*.jsonl"):
            if not path.is_file():
                continue
            if not _matches_session_filter(reader, path):
                continue
            if not _matches_work_dir(reader, path):
                continue
            mtime = _read_mtime(path)
            if mtime is None:
                continue
            yield path, mtime
    except OSError:
        return


def _matches_session_filter(reader, path: Path) -> bool:
    session_id_filter = reader._session_id_filter
    if not session_id_filter or _follow_workspace(reader):
        return True
    try:
        return str(session_id_filter).lower() in str(path).lower()
    except Exception:
        return True


def _matches_work_dir(reader, path: Path) -> bool:
    if not reader._work_dir:
        return True
    cwd = extract_cwd_from_log(reader, path)
    return bool(cwd and cwd == reader._work_dir)


def _read_mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _follow_workspace(reader) -> bool:
    from ..state import follow_workspace_sessions

    return follow_workspace_sessions(reader)


def bind_preferred_log(reader, latest: Path) -> Path:
    reader._preferred_log = latest
    debug_log_reader(f"Scan found: {latest}")
    return latest


__all__ = ["bind_preferred_log", "candidate_logs"]
