from __future__ import annotations

import time
from typing import Any

from ...log_entries import extract_entry, extract_message
from .events import message_event as _message_event
from .service import read_matching_since as _read_matching_since


def read_since(
    reader,
    state: dict[str, Any],
    timeout: float,
    block: bool,
) -> tuple[str | None, dict[str, Any]]:
    return _read_matching_since(
        reader,
        state,
        timeout,
        block,
        extractor=extract_message,
        stop_on_missing_timeout=False,
    )


def read_event_since(
    reader,
    state: dict[str, Any],
    timeout: float,
    block: bool,
) -> tuple[tuple[str, str] | None, dict[str, Any]]:
    deadline = time.time() + timeout
    current_state = dict(state or {})
    while True:
        remaining = max(0.0, deadline - time.time()) if block else 0.0
        entry, current_state = read_entry_since(reader, current_state, remaining, block=block)
        if entry is None:
            return None, current_state
        event = _message_event(entry)
        if event is not None:
            return event, current_state
        if not block:
            continue
        if time.time() >= deadline:
            return None, current_state


def read_entry_since(
    reader,
    state: dict[str, Any],
    timeout: float,
    block: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    return _read_matching_since(
        reader,
        state,
        timeout,
        block,
        extractor=extract_entry,
        stop_on_missing_timeout=True,
    )


__all__ = ['read_entry_since', 'read_event_since', 'read_since']
