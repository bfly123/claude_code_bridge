from __future__ import annotations

import json
from typing import Any

from ..session_selection import latest_session
from .context import build_cursor, current_state_payload
from .reader_state import refresh_latest_session
from .service_runtime_flow import process_session, wait_until_next_poll
from .service_runtime_session import missing_session_result


def read_since(
    reader,
    state: dict[str, Any],
    timeout: float,
    block: bool,
) -> tuple[str | None, dict[str, Any]]:
    cursor = build_cursor(state, timeout=timeout)

    while True:
        refresh_latest_session(reader, cursor)
        session = latest_session(reader)
        result = read_current_session(reader, cursor, session=session, block=block)
        if result is not None:
            return result


def read_current_session(reader, cursor, *, session, block: bool):
    if session is None or not session.exists():
        return missing_session_result(reader, cursor, block=block)

    try:
        return process_session(reader, cursor, session=session, block=block)
    except (OSError, json.JSONDecodeError):
        if not block:
            return None, current_state_payload(cursor, session=session)
        return wait_until_next_poll(reader, cursor, session=session)


__all__ = ["read_since"]
