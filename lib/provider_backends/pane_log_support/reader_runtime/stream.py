from __future__ import annotations

import time
from pathlib import Path

from ..parsing import extract_assistant_blocks, extract_conversation_pairs, strip_ansi
from .state import resolve_log_path


def read_since_message(reader, state: dict, *, timeout: float, block: bool):
    return _read_until(reader, state, timeout=timeout, block=block, extractor=_extract_latest_message, empty_value=None)


def read_since_events(reader, state: dict, *, timeout: float, block: bool):
    return _read_until(reader, state, timeout=timeout, block=block, extractor=_extract_events, empty_value=[])


def _read_until(reader, state: dict, *, timeout: float, block: bool, extractor, empty_value):
    deadline = time.time() + max(0.0, float(timeout)) if block else time.time()
    current_state = dict(state or {})

    while True:
        log_path = resolve_log_path(reader)
        if log_path is None or not log_path.exists():
            if not block or time.time() >= deadline:
                return empty_value, current_state
            time.sleep(reader._poll_interval)
            continue

        current_state = _reset_state_for_new_path(current_state, log_path)
        payload, current_state = _read_new_payload(log_path, current_state, extractor=extractor, empty_value=empty_value)
        if payload:
            return payload, current_state
        if not block or time.time() >= deadline:
            return empty_value, current_state
        time.sleep(reader._poll_interval)


def _reset_state_for_new_path(state: dict, log_path: Path) -> dict:
    if state.get('pane_log_path') == log_path:
        return state
    next_state = dict(state)
    next_state['pane_log_path'] = log_path
    next_state['offset'] = 0
    return next_state


def _read_new_payload(log_path: Path, state: dict, *, extractor, empty_value):
    offset = int(state.get('offset') or 0)
    size = _read_size(log_path)
    if size is None:
        return empty_value, state
    if size < offset:
        offset = 0
    if size == offset:
        return empty_value, state

    data = _read_bytes(log_path, offset)
    if data is None:
        return empty_value, state
    new_offset = offset + len(data)
    clean = strip_ansi(data.decode('utf-8', errors='replace'))
    return extractor(clean), {'pane_log_path': log_path, 'offset': new_offset}


def _read_size(log_path: Path) -> int | None:
    try:
        return log_path.stat().st_size
    except OSError:
        return None


def _read_bytes(log_path: Path, offset: int) -> bytes | None:
    try:
        with log_path.open('rb') as handle:
            handle.seek(offset)
            return handle.read()
    except OSError:
        return None


def _extract_latest_message(clean: str):
    blocks = extract_assistant_blocks(clean)
    return blocks[-1] if blocks else None


def _extract_events(clean: str):
    events: list[tuple[str, str]] = []
    for user_msg, assistant_msg in extract_conversation_pairs(clean):
        if user_msg:
            events.append(('user', user_msg))
        if assistant_msg:
            events.append(('assistant', assistant_msg))
    return events


__all__ = ["read_since_events", "read_since_message"]
