from __future__ import annotations

from pathlib import Path

from ..incremental_io import read_incremental_jsonl
from ..parsing import extract_message, structured_event


def read_new_messages(reader, session: Path, state: dict) -> tuple[str | None, dict]:
    offset = int(state.get('offset') or 0)
    carry = state.get('carry') or b''
    entries, updated = read_incremental_jsonl(session, offset, carry)
    latest: str | None = None
    for entry in entries:
        msg = extract_message(entry, 'assistant')
        if msg:
            latest = msg
    return latest, {'session_path': session, 'offset': updated['offset'], 'carry': updated['carry']}


def read_new_events(reader, session: Path, state: dict) -> tuple[list[tuple[str, str]], dict]:
    offset = int(state.get('offset') or 0)
    carry = state.get('carry') or b''
    entries, updated = read_incremental_jsonl(session, offset, carry)
    events: list[tuple[str, str]] = []
    for entry in entries:
        user_msg = extract_message(entry, 'user')
        if user_msg:
            events.append(('user', user_msg))
            continue
        assistant_msg = extract_message(entry, 'assistant')
        if assistant_msg:
            events.append(('assistant', assistant_msg))
    return events, {'session_path': session, 'offset': updated['offset'], 'carry': updated['carry']}


def read_new_entries(reader, session: Path, state: dict) -> tuple[list[dict], dict]:
    offset = int(state.get('offset') or 0)
    carry = state.get('carry') or b''
    raw_entries, updated = read_incremental_jsonl(session, offset, carry)
    entries: list[dict] = []
    for entry in raw_entries:
        structured = structured_event(entry)
        if structured is not None:
            entries.append(structured)
    return entries, {'session_path': session, 'offset': updated['offset'], 'carry': updated['carry']}


__all__ = ['read_new_entries', 'read_new_events', 'read_new_messages']
