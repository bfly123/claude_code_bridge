from __future__ import annotations

from pathlib import Path

from ...debug import debug_log_reader
from .candidates import bind_preferred_log, candidate_logs


def scan_latest(reader) -> Path | None:
    latest: Path | None = None
    latest_mtime = -1.0
    for path, mtime in candidate_logs(reader):
        if mtime >= latest_mtime:
            latest = path
            latest_mtime = mtime
    return latest


def latest_log(reader) -> Path | None:
    preferred = reader._preferred_log
    if _preferred_is_bound(reader, preferred):
        debug_log_reader(f"Using preferred log (bound): {preferred}")
        return preferred

    if preferred and preferred.exists():
        latest = scan_latest(reader)
        chosen = _select_preferred_or_latest(reader, preferred, latest)
        if chosen is not None:
            return chosen

    debug_log_reader("No valid preferred log, scanning...")
    latest = scan_latest(reader)
    if latest is None:
        return None
    return bind_preferred_log(reader, latest)


def _preferred_is_bound(reader, preferred: Path | None) -> bool:
    if preferred is None or not preferred.exists():
        return False
    from ..state import follow_workspace_sessions

    return bool(reader._session_id_filter and not follow_workspace_sessions(reader))


def _select_preferred_or_latest(reader, preferred: Path, latest: Path | None) -> Path | None:
    if latest is None or latest == preferred:
        debug_log_reader(f"Using preferred log: {preferred}")
        return preferred
    try:
        preferred_mtime = preferred.stat().st_mtime
        latest_mtime = latest.stat().st_mtime
        if latest_mtime > preferred_mtime:
            reader._preferred_log = latest
            debug_log_reader(f"Preferred log stale; switching to latest: {latest}")
            return latest
    except OSError:
        reader._preferred_log = latest
        debug_log_reader(f"Preferred log stat failed; switching to latest: {latest}")
        return latest
    debug_log_reader(f"Using preferred log: {preferred}")
    return preferred


__all__ = ["latest_log", "scan_latest"]
