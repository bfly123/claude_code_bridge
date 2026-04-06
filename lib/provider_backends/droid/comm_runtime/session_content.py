from __future__ import annotations

import json
from pathlib import Path

from .parsing import extract_message
from .session_selection import latest_session


def capture_state(reader) -> dict[str, object]:
    session = _latest_session_path(reader)
    offset = 0
    if session is not None:
        try:
            offset = session.stat().st_size
        except OSError:
            offset = 0
    return {"session_path": session, "offset": offset, "carry": b""}


def latest_message(reader) -> str | None:
    last: str | None = None
    for entry in _iter_session_entries(reader):
        msg = extract_message(entry, "assistant")
        if msg:
            last = msg
    return last


def latest_conversations(reader, n: int = 1) -> list[tuple[str, str]]:
    if int(n) <= 0:
        return []
    pairs: list[tuple[str, str]] = []
    last_user: str | None = None
    for entry in _iter_session_entries(reader):
        user_msg = extract_message(entry, "user")
        if user_msg:
            last_user = user_msg
            continue
        assistant_msg = extract_message(entry, "assistant")
        if assistant_msg:
            pairs.append((last_user or "", assistant_msg))
            last_user = None
    return pairs[-max(1, int(n)) :]


def _iter_session_entries(reader):
    session = _latest_session_path(reader)
    if session is None:
        return
    try:
        with session.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                entry = _parse_entry(line)
                if entry is not None:
                    yield entry
    except OSError:
        return


def _latest_session_path(reader) -> Path | None:
    session = latest_session(reader)
    if not session or not session.exists():
        return None
    return session


def _parse_entry(line: str):
    text = line.strip()
    if not text:
        return None
    try:
        entry = json.loads(text)
    except Exception:
        return None
    return entry if isinstance(entry, dict) else None


__all__ = ["capture_state", "latest_conversations", "latest_message"]
