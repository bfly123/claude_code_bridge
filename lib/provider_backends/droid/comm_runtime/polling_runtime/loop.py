from __future__ import annotations

import time

from ..session_selection import latest_session
from .entries import read_new_events, read_new_messages


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

        if current_state.get('session_path') != session:
            current_state['session_path'] = session
            current_state['offset'] = 0
            current_state['carry'] = b''

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

        if current_state.get('session_path') != session:
            current_state['session_path'] = session
            current_state['offset'] = 0
            current_state['carry'] = b''

        events, current_state = read_new_events(session, current_state)
        if events:
            return events, current_state

        if not block or time.time() >= deadline:
            return [], current_state
        time.sleep(reader._poll_interval)


__all__ = ['read_since', 'read_since_events']
