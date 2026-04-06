from __future__ import annotations

from pathlib import Path


def set_preferred_session(reader, session_path: Path | None) -> None:
    if not session_path:
        return
    try:
        candidate = session_path if isinstance(session_path, Path) else Path(str(session_path)).expanduser()
    except Exception:
        return
    if candidate.exists():
        reader._preferred_session = candidate


def set_session_id_hint(reader, session_id: str | None) -> None:
    if not session_id:
        return
    reader._session_id_hint = str(session_id).strip()


__all__ = ['set_preferred_session', 'set_session_id_hint']
