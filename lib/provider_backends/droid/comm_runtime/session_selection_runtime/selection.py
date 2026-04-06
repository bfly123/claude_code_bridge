from __future__ import annotations

import os

from .id_lookup import find_session_by_id
from .scanning import scan_latest_session, scan_latest_session_any_project


def latest_session(reader):
    preferred = reader._preferred_session
    scanned = scan_latest_session(reader)

    if preferred and preferred.exists():
        if scanned and scanned.exists():
            try:
                pref_mtime = preferred.stat().st_mtime
                scan_mtime = scanned.stat().st_mtime
                if scan_mtime > pref_mtime:
                    reader._preferred_session = scanned
                    return scanned
            except OSError:
                pass
        return preferred

    by_id = find_session_by_id(reader)
    if by_id:
        reader._preferred_session = by_id
        return by_id

    if scanned:
        reader._preferred_session = scanned
        return scanned

    if os.environ.get('DROID_ALLOW_ANY_PROJECT_SCAN') in ('1', 'true', 'yes'):
        any_latest = scan_latest_session_any_project(reader)
        if any_latest:
            reader._preferred_session = any_latest
            return any_latest
    return None


__all__ = ['latest_session']
