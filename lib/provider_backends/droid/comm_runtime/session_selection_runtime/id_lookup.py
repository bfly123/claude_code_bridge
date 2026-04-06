from __future__ import annotations

from pathlib import Path


def find_session_by_id(reader) -> Path | None:
    session_id = (reader._session_id_hint or '').strip()
    if not session_id or not reader.root.exists():
        return None
    latest: Path | None = None
    latest_mtime = -1.0
    try:
        for path in reader.root.glob(f'**/{session_id}.jsonl'):
            if not path.is_file():
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime >= latest_mtime:
                latest_mtime = mtime
                latest = path
    except Exception:
        return None
    return latest


__all__ = ['find_session_by_id']
