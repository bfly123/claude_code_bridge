from __future__ import annotations

import json
from pathlib import Path

from ..parsing import extract_message


def read_new_messages(
    session: Path,
    state: dict[str, object],
) -> tuple[str | None, dict[str, object]]:
    entries, new_state = read_new_entries(session, state)
    latest: str | None = None
    for entry in entries:
        msg = extract_message(entry, 'assistant')
        if msg:
            latest = msg
    return latest, new_state


def read_new_events(
    session: Path,
    state: dict[str, object],
) -> tuple[list[tuple[str, str]], dict[str, object]]:
    entries, new_state = read_new_entries(session, state)
    events: list[tuple[str, str]] = []
    for entry in entries:
        event = _entry_event(entry)
        if event is not None:
            events.append(event)
    return events, new_state


def read_new_entries(
    session: Path,
    state: dict[str, object],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    offset, carry = _reader_state(state)
    size = _session_size(session)
    if size is None:
        return [], state
    offset, carry = _normalized_reader_state(size=size, offset=offset, carry=carry)
    data = _read_bytes(session, offset)
    if data is None:
        return [], state
    new_offset = offset + len(data)
    lines, carry = _split_buffer_lines(carry, data)
    entries = _parse_jsonl_entries(lines)
    new_state = {'session_path': session, 'offset': new_offset, 'carry': carry}
    return entries, new_state


def _entry_event(entry: dict[str, object]) -> tuple[str, str] | None:
    user_msg = extract_message(entry, 'user')
    if user_msg:
        return 'user', user_msg
    assistant_msg = extract_message(entry, 'assistant')
    if assistant_msg:
        return 'assistant', assistant_msg
    return None


def _reader_state(state: dict[str, object]) -> tuple[int, bytes]:
    return int(state.get('offset') or 0), state.get('carry') or b''


def _session_size(session: Path) -> int | None:
    try:
        return session.stat().st_size
    except OSError:
        return None


def _normalized_reader_state(*, size: int, offset: int, carry: bytes) -> tuple[int, bytes]:
    if size < offset:
        return 0, b''
    return offset, carry


def _read_bytes(session: Path, offset: int) -> bytes | None:
    try:
        with session.open('rb') as handle:
            handle.seek(offset)
            return handle.read()
    except OSError:
        return None


def _split_buffer_lines(carry: bytes, data: bytes) -> tuple[list[bytes], bytes]:
    buffer = carry + data
    lines = buffer.split(b'\n')
    if buffer and not buffer.endswith(b'\n'):
        return lines[:-1], lines[-1]
    return lines, b''


def _parse_jsonl_entries(lines: list[bytes]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for raw in lines:
        entry = _parse_jsonl_entry(raw)
        if entry is not None:
            entries.append(entry)
    return entries


def _parse_jsonl_entry(raw: bytes) -> dict[str, object] | None:
    line = raw.strip()
    if not line:
        return None
    try:
        entry = json.loads(line.decode('utf-8', errors='replace'))
    except Exception:
        return None
    return entry if isinstance(entry, dict) else None


__all__ = ['read_new_entries', 'read_new_events', 'read_new_messages']
