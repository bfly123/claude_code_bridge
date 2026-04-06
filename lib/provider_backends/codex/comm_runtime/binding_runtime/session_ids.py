from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import load_first_entry, read_first_line

SESSION_ID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def extract_session_id(log_path: Path) -> str | None:
    session_id = _extract_from_path(log_path)
    if session_id:
        return session_id

    first_line = read_first_line(log_path)
    if not first_line:
        return None

    session_id = _match_session_id(first_line)
    if session_id:
        return session_id

    entry = load_first_entry(log_path)
    if entry is None:
        return None
    return _extract_from_entry(entry)


def _extract_from_path(log_path: Path) -> str | None:
    for source in (log_path.stem, log_path.name):
        session_id = _match_session_id(source)
        if session_id:
            return session_id
    return None


def _extract_from_entry(entry: dict[str, Any]) -> str | None:
    payload = entry.get("payload", {}) if isinstance(entry, dict) else {}
    nested_session = payload.get("session", {}) if isinstance(payload, dict) else {}
    candidates = [
        entry.get("session_id"),
        payload.get("id") if isinstance(payload, dict) else None,
        nested_session.get("id") if isinstance(nested_session, dict) else None,
    ]
    for candidate in candidates:
        session_id = _match_session_id(candidate)
        if session_id:
            return session_id
    return None


def _match_session_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = SESSION_ID_PATTERN.search(value)
    return match.group(0) if match else None


__all__ = ["SESSION_ID_PATTERN", "extract_session_id"]
