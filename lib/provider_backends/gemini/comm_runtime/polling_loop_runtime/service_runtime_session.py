from __future__ import annotations

import json
import time

from ..session_content import read_session_json
from .reader_state import missing_session_state


def missing_session_result(reader, cursor, *, block: bool):
    if not block:
        return None, missing_session_state(cursor)
    time.sleep(reader._poll_interval)
    if time.time() >= cursor.deadline:
        return None, missing_session_state(cursor)
    return None


def read_complete_session_json(reader, session):
    data = read_session_json(reader, session)
    if data is None:
        raise json.JSONDecodeError("Gemini session JSON is incomplete", "", 0)
    return data


__all__ = [
    'missing_session_result',
    'read_complete_session_json',
]
