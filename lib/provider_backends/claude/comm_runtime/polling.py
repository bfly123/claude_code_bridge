from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .incremental_io import read_incremental_jsonl
from .parsing import extract_message, structured_event
from .session_selection import latest_session
from .subagents import read_new_subagent_events, subagent_state_for_session


def read_since(reader, state: dict[str, Any], timeout: float, block: bool) -> tuple[str | None, dict[str, Any]]:
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

        message, current_state = read_new_messages(reader, session, current_state)
        if message:
            return message, current_state

        if not block or time.time() >= deadline:
            return None, current_state
        time.sleep(reader._poll_interval)


def read_since_events(reader, state: dict[str, Any], timeout: float, block: bool) -> tuple[list[tuple[str, str]], dict[str, Any]]:
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
            if reader._include_subagents:
                current_state["subagents"] = subagent_state_for_session(reader, session, start_from_end=False)

        events, current_state = read_new_events(reader, session, current_state)
        sub_events: list[tuple[str, str]] = []
        if reader._include_subagents:
            sub_events, sub_state = read_new_subagent_events(reader, session, current_state)
            current_state["subagents"] = sub_state
        if events or sub_events:
            if sub_events:
                events.extend(sub_events)
            return events, current_state

        if not block or time.time() >= deadline:
            return [], current_state
        time.sleep(reader._poll_interval)


def read_since_entries(reader, state: dict[str, Any], timeout: float, block: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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

        entries, current_state = read_new_entries(reader, session, current_state)
        if entries:
            return entries, current_state

        if not block or time.time() >= deadline:
            return [], current_state
        time.sleep(reader._poll_interval)


def read_new_messages(reader, session: Path, state: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    offset = int(state.get("offset") or 0)
    carry = state.get("carry") or b""
    entries, updated = read_incremental_jsonl(session, offset, carry)
    latest: str | None = None
    for entry in entries:
        msg = extract_message(entry, "assistant")
        if msg:
            latest = msg
    return latest, {"session_path": session, "offset": updated["offset"], "carry": updated["carry"]}


def read_new_events(reader, session: Path, state: dict[str, Any]) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    offset = int(state.get("offset") or 0)
    carry = state.get("carry") or b""
    entries, updated = read_incremental_jsonl(session, offset, carry)
    events: list[tuple[str, str]] = []
    for entry in entries:
        user_msg = extract_message(entry, "user")
        if user_msg:
            events.append(("user", user_msg))
            continue
        assistant_msg = extract_message(entry, "assistant")
        if assistant_msg:
            events.append(("assistant", assistant_msg))
    return events, {"session_path": session, "offset": updated["offset"], "carry": updated["carry"]}


def read_new_entries(reader, session: Path, state: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    offset = int(state.get("offset") or 0)
    carry = state.get("carry") or b""
    raw_entries, updated = read_incremental_jsonl(session, offset, carry)
    entries: list[dict[str, Any]] = []
    for entry in raw_entries:
        structured = structured_event(entry)
        if structured is not None:
            entries.append(structured)
    return entries, {"session_path": session, "offset": updated["offset"], "carry": updated["carry"]}


__all__ = [
    "read_new_entries",
    "read_new_events",
    "read_new_messages",
    "read_since",
    "read_since_entries",
    "read_since_events",
]
