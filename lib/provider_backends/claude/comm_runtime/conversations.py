from __future__ import annotations

import json

from .parsing import extract_message
from .session_selection import latest_session


def latest_message(reader) -> str | None:
    session = latest_session(reader)
    if not session or not session.exists():
        return None
    last: str | None = None
    try:
        with session.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                msg = extract_message(entry, "assistant")
                if msg:
                    last = msg
    except OSError:
        return None
    return last


def latest_conversations(reader, n: int) -> list[tuple[str, str]]:
    session = latest_session(reader)
    if not session or not session.exists():
        return []
    pairs: list[tuple[str, str]] = []
    last_user: str | None = None
    try:
        with session.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                user_msg = extract_message(entry, "user")
                if user_msg:
                    last_user = user_msg
                    continue
                assistant_msg = extract_message(entry, "assistant")
                if assistant_msg:
                    pairs.append((last_user or "", assistant_msg))
                    last_user = None
    except OSError:
        return []
    return pairs[-max(1, int(n)) :]


__all__ = ["latest_conversations", "latest_message"]
