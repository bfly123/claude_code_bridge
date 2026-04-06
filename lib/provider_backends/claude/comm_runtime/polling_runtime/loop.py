from __future__ import annotations

import time

from ..subagents import read_new_subagent_events
from .common import poll_session_loop
from .entries import read_new_entries, read_new_events, read_new_messages


def read_since(reader, state: dict, timeout: float, block: bool) -> tuple[str | None, dict]:
    current_state = dict(state or {})
    while True:
        session, current_state, exhausted = poll_session_loop(reader, current_state, timeout, block)
        if exhausted:
            return None, current_state
        assert session is not None
        message, current_state = read_new_messages(reader, session, current_state)
        if message:
            return message, current_state
        if not block:
            return None, current_state
        time.sleep(reader._poll_interval)


def read_since_events(reader, state: dict, timeout: float, block: bool) -> tuple[list[tuple[str, str]], dict]:
    current_state = dict(state or {})
    while True:
        session, current_state, exhausted = poll_session_loop(
            reader,
            current_state,
            timeout,
            block,
            include_subagents=reader._include_subagents,
        )
        if exhausted:
            return [], current_state
        assert session is not None
        events, current_state = read_new_events(reader, session, current_state)
        sub_events: list[tuple[str, str]] = []
        if reader._include_subagents:
            sub_events, sub_state = read_new_subagent_events(reader, session, current_state)
            current_state['subagents'] = sub_state
        if events or sub_events:
            if sub_events:
                events.extend(sub_events)
            return events, current_state
        if not block:
            return [], current_state
        time.sleep(reader._poll_interval)


def read_since_entries(reader, state: dict, timeout: float, block: bool) -> tuple[list[dict], dict]:
    current_state = dict(state or {})
    while True:
        session, current_state, exhausted = poll_session_loop(reader, current_state, timeout, block)
        if exhausted:
            return [], current_state
        assert session is not None
        entries, current_state = read_new_entries(reader, session, current_state)
        if entries:
            return entries, current_state
        if not block:
            return [], current_state
        time.sleep(reader._poll_interval)


__all__ = ['read_since', 'read_since_entries', 'read_since_events']
