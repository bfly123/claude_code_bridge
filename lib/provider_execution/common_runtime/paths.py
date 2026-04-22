from __future__ import annotations

from pathlib import Path


def normalize_session_path(value: object) -> str:
    normalized = expand_path(value)
    return str(normalized) if normalized is not None else ''


def preferred_session_path(
    session_path: object,
    session_ref: str | None,
    session_file: object | None = None,
) -> Path | None:
    preferred = expand_path(session_path)
    if preferred is not None:
        return preferred
    explicit_file = expand_path(session_file)
    if explicit_file is not None:
        return explicit_file
    ref = str(session_ref or '').strip()
    if not looks_like_session_path(ref):
        return None
    return expand_path(ref)


def expand_path(value: object) -> Path | None:
    if isinstance(value, Path):
        return value.expanduser()
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return Path(value).expanduser()
    except Exception:
        return None


def looks_like_session_path(value: str) -> bool:
    if not value:
        return False
    path_markers = ('.json', '.jsonl', '/', '\\')
    return value.startswith('~') or any(marker in value for marker in path_markers)


__all__ = ['normalize_session_path', 'preferred_session_path']
