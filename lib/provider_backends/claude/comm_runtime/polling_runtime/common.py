from __future__ import annotations

import time

from ..session_selection import latest_session
from ..subagents import subagent_state_for_session


def poll_session_loop(reader, state: dict, timeout: float, block: bool, *, include_subagents: bool = False):
    deadline = time.time() + max(0.0, float(timeout)) if block else time.time()
    current_state = dict(state or {})

    while True:
        session = latest_session(reader)
        if session is None or not session.exists():
            if not block or time.time() >= deadline:
                return None, current_state, True
            time.sleep(reader._poll_interval)
            continue

        if current_state.get('session_path') != session:
            current_state['session_path'] = session
            current_state['offset'] = 0
            current_state['carry'] = b''
            if include_subagents:
                current_state['subagents'] = subagent_state_for_session(reader, session, start_from_end=False)
        return session, current_state, False


__all__ = ['poll_session_loop']
