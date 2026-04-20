from __future__ import annotations

import time

from ..session_selection import latest_session
from .entries import read_new_events, read_new_messages


def _deadline(timeout: float, *, block: bool) -> float:
    return time.time() + max(0.0, float(timeout)) if block else time.time()


def _read_session(reader):
    session = latest_session(reader)
    if session is None or not session.exists():
        return None
    return session


def _reset_state_for_session(current_state: dict[str, object], session) -> dict[str, object]:
    if current_state.get('session_path') == session:
        return current_state
    current_state['session_path'] = session
    current_state['offset'] = 0
    current_state['carry'] = b''
    return current_state


def _read_until_result(
    reader,
    state: dict[str, object],
    timeout: float,
    block: bool,
    *,
    read_fn,
    empty_value,
):
    deadline = _deadline(timeout, block=block)
    current_state = dict(state or {})

    while True:
        session = _read_session(reader)
        if session is None:
            if not block or time.time() >= deadline:
                return empty_value, current_state
            time.sleep(reader._poll_interval)
            continue

        current_state = _reset_state_for_session(current_state, session)
        payload, current_state = read_fn(session, current_state)
        if payload:
            return payload, current_state

        if not block or time.time() >= deadline:
            return empty_value, current_state
        time.sleep(reader._poll_interval)


def read_since(reader, state: dict[str, object], timeout: float, block: bool) -> tuple[str | None, dict[str, object]]:
    return _read_until_result(
        reader,
        state,
        timeout,
        block,
        read_fn=read_new_messages,
        empty_value=None,
    )


def read_since_events(
    reader,
    state: dict[str, object],
    timeout: float,
    block: bool,
) -> tuple[list[tuple[str, str]], dict[str, object]]:
    return _read_until_result(
        reader,
        state,
        timeout,
        block,
        read_fn=read_new_events,
        empty_value=[],
    )


__all__ = ['read_since', 'read_since_events']
