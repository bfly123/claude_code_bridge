from __future__ import annotations

import time

from ..polling_detection import handle_unknown_baseline, hash_content, new_message_from_growth
from ..session_content import extract_last_gemini
from .context import current_state_payload, update_from_values, update_last_gemini
from .reader_state import (
    gemini_reply_changed,
    reply_state_payload,
    session_stat_values,
    should_wait_for_forced_read,
)
from .service_runtime_session import read_complete_session_json
from .waiting import wait_or_timeout

def process_session(reader, cursor, *, session, block: bool):
    current_mtime, current_mtime_ns, current_size = session_stat_values(session)
    if should_wait_for_forced_read(
        reader,
        cursor,
        current_mtime_ns=current_mtime_ns,
        current_size=current_size,
        block=block,
    ):
        return wait_or_timeout(reader, cursor=cursor, session=session)

    data = read_complete_session_json(reader, session)
    current_count = len(data.get("messages", []))
    if cursor.unknown_baseline:
        return handle_unknown_baseline_result(
            reader,
            cursor,
            data,
            session=session,
            current_count=current_count,
            current_mtime=current_mtime,
            current_mtime_ns=current_mtime_ns,
            current_size=current_size,
            block=block,
        )

    result = detect_reply_result(
        cursor,
        data,
        session=session,
        current_count=current_count,
        current_mtime=current_mtime,
        current_mtime_ns=current_mtime_ns,
        current_size=current_size,
    )
    if result is not None:
        return result

    update_cursor_from_session(
        cursor,
        data,
        session=session,
        current_count=current_count,
        current_mtime=current_mtime,
        current_mtime_ns=current_mtime_ns,
        current_size=current_size,
    )
    if not block:
        return None, current_state_payload(cursor, session=session)
    return wait_until_next_poll(reader, cursor, session=session)

def handle_unknown_baseline_result(
    reader,
    cursor,
    data,
    *,
    session,
    current_count: int,
    current_mtime: float,
    current_mtime_ns: int,
    current_size: int,
    block: bool,
):
    result = handle_unknown_baseline(
        data,
        session=session,
        current_count=current_count,
        current_mtime=current_mtime,
        current_mtime_ns=current_mtime_ns,
        current_size=current_size,
        prev_mtime_ns=cursor.prev_mtime_ns,
        prev_size=cursor.prev_size,
    )
    update_cursor_from_session(
        cursor,
        data,
        session=session,
        current_count=current_count,
        current_mtime=current_mtime,
        current_mtime_ns=current_mtime_ns,
        current_size=current_size,
    )
    cursor.unknown_baseline = False
    if result is not None:
        return result
    if not block:
        return None, current_state_payload(cursor, session=session)
    return wait_until_next_poll(reader, cursor, session=session)

def detect_reply_result(
    cursor,
    data,
    *,
    session,
    current_count: int,
    current_mtime: float,
    current_mtime_ns: int,
    current_size: int,
):
    messages = data.get("messages", [])
    if current_count > cursor.prev_count:
        return new_message_from_growth(
            messages[cursor.prev_count:],
            session=session,
            current_count=current_count,
            current_mtime=current_mtime,
            current_mtime_ns=current_mtime_ns,
            current_size=current_size,
            prev_last_gemini_id=cursor.prev_last_gemini_id,
            prev_last_gemini_hash=cursor.prev_last_gemini_hash,
        )
    return changed_last_reply_result(
        cursor,
        data,
        session=session,
        current_count=current_count,
        current_mtime=current_mtime,
        current_mtime_ns=current_mtime_ns,
        current_size=current_size,
    )

def changed_last_reply_result(
    cursor,
    data,
    *,
    session,
    current_count: int,
    current_mtime: float,
    current_mtime_ns: int,
    current_size: int,
):
    last = extract_last_gemini(data)
    if not last:
        return None
    last_id, content = last
    if not content:
        return None
    current_hash = hash_content(content)
    if not gemini_reply_changed(cursor, last_id=last_id, current_hash=current_hash):
        return None
    return content, reply_state_payload(
        session=session,
        current_count=current_count,
        current_mtime=current_mtime,
        current_mtime_ns=current_mtime_ns,
        current_size=current_size,
        last_id=last_id,
        current_hash=current_hash,
    )

def update_cursor_from_session(
    cursor,
    data,
    *,
    session,
    current_count: int,
    current_mtime: float,
    current_mtime_ns: int,
    current_size: int,
) -> None:
    cursor.last_forced_read = time.time()
    update_from_values(
        cursor,
        session=session,
        current_count=current_count,
        current_mtime=current_mtime,
        current_mtime_ns=current_mtime_ns,
        current_size=current_size,
    )
    update_last_gemini(cursor, data)

def wait_until_next_poll(reader, cursor, *, session):
    time.sleep(reader._poll_interval)
    if time.time() >= cursor.deadline:
        return None, current_state_payload(cursor, session=session)
    return None


__all__ = ['process_session', 'wait_until_next_poll']
