from __future__ import annotations

import json
import time
from pathlib import Path

from .parsing import extract_message
from .session_selection import latest_session


def read_since(reader, state: dict[str, object], timeout: float, block: bool) -> tuple[str | None, dict[str, object]]:
    deadline = time.time() + max(0.0, float(timeout)) if block else time.time()
    current_state = dict(state or {})

    while True:
        session = latest_session(reader)
        if session is None or not session.exists():
            if not block or time.time() >= deadline:
                return None, current_state
            time.sleep(reader._poll_interval)
            continue

        if current_state.get("session_path") != session:
            current_state["session_path"] = session
            current_state["offset"] = 0
            current_state["carry"] = b""

        message, current_state = read_new_messages(session, current_state)
        if message:
            return message, current_state

        if not block or time.time() >= deadline:
            return None, current_state
        time.sleep(reader._poll_interval)


def read_since_events(
    reader,
    state: dict[str, object],
    timeout: float,
    block: bool,
) -> tuple[list[tuple[str, str]], dict[str, object]]:
    deadline = time.time() + max(0.0, float(timeout)) if block else time.time()
    current_state = dict(state or {})

    while True:
        session = latest_session(reader)
        if session is None or not session.exists():
            if not block or time.time() >= deadline:
                return [], current_state
            time.sleep(reader._poll_interval)
            continue

        if current_state.get("session_path") != session:
            current_state["session_path"] = session
            current_state["offset"] = 0
            current_state["carry"] = b""

        events, current_state = read_new_events(session, current_state)
        if events:
            return events, current_state

        if not block or time.time() >= deadline:
            return [], current_state
        time.sleep(reader._poll_interval)


def read_new_messages(session: Path, state: dict[str, object]) -> tuple[str | None, dict[str, object]]:
    entries, new_state = read_new_entries(session, state)
    latest: str | None = None
    for entry in entries:
        msg = extract_message(entry, "assistant")
        if msg:
            latest = msg
    return latest, new_state


def read_new_events(session: Path, state: dict[str, object]) -> tuple[list[tuple[str, str]], dict[str, object]]:
    entries, new_state = read_new_entries(session, state)
    events: list[tuple[str, str]] = []
    for entry in entries:
        user_msg = extract_message(entry, "user")
        if user_msg:
            events.append(("user", user_msg))
            continue
        assistant_msg = extract_message(entry, "assistant")
        if assistant_msg:
            events.append(("assistant", assistant_msg))
    return events, new_state


def read_new_entries(session: Path, state: dict[str, object]) -> tuple[list[dict[str, object]], dict[str, object]]:
    offset = int(state.get("offset") or 0)
    carry = state.get("carry") or b""
    try:
        size = session.stat().st_size
    except OSError:
        return [], state

    if size < offset:
        offset = 0
        carry = b""

    try:
        with session.open("rb") as handle:
            handle.seek(offset)
            data = handle.read()
    except OSError:
        return [], state

    new_offset = offset + len(data)
    buf = carry + data
    lines = buf.split(b"\n")
    if buf and not buf.endswith(b"\n"):
        carry = lines.pop()
    else:
        carry = b""

    entries: list[dict[str, object]] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(entry, dict):
            entries.append(entry)

    new_state = {"session_path": session, "offset": new_offset, "carry": carry}
    return entries, new_state


__all__ = [
    "read_new_entries",
    "read_new_events",
    "read_new_messages",
    "read_since",
    "read_since_events",
]
