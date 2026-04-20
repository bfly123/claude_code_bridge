from __future__ import annotations

import os
from pathlib import Path

from ..indexing import parse_sessions_index
from ..membership import session_belongs_to_current_project
from .scan import scan_latest_session, scan_latest_session_any_project


def latest_session(reader) -> Path | None:
    preferred = _preferred_session(reader)
    index_session = parse_sessions_index(reader)
    scanned = scan_latest_session(reader) if index_session is None else None
    if preferred is not None:
        return preferred
    if getattr(reader, '_preferred_session_locked', False):
        return None
    if index_session:
        reader._preferred_session = index_session
        return index_session
    if scanned:
        reader._preferred_session = scanned
        return scanned
    if os.environ.get('CLAUDE_ALLOW_ANY_PROJECT_SCAN') in ('1', 'true', 'yes'):
        any_latest = scan_latest_session_any_project(reader)
        if any_latest:
            reader._preferred_session = any_latest
            return any_latest
    return None


def _preferred_session(reader) -> Path | None:
    preferred = reader._preferred_session
    if preferred and not session_belongs_to_current_project(reader, preferred):
        _clear_preferred_session(reader)
        preferred = None
    if preferred and preferred.exists():
        if getattr(reader, '_preferred_session_locked', False):
            return preferred
        candidate = _newer_candidate(preferred, parse_sessions_index(reader), scan_latest_session(reader))
        if candidate is not None:
            reader._preferred_session = candidate
            return candidate
        return preferred
    return None


def _clear_preferred_session(reader) -> None:
    reader._preferred_session = None
    reader._preferred_session_locked = False


def _newer_candidate(preferred: Path, index_session: Path | None, scanned: Path | None) -> Path | None:
    try:
        preferred_mtime = preferred.stat().st_mtime
    except OSError:
        return None
    for candidate in (index_session, scanned):
        if not candidate or not candidate.exists():
            continue
        try:
            if candidate.stat().st_mtime > preferred_mtime:
                return candidate
        except OSError:
            continue
    return None


__all__ = ['latest_session']
