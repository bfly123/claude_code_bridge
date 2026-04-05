from __future__ import annotations

import json
import time
from typing import Any

from ..polling_detection import handle_unknown_baseline, hash_content, new_message_from_growth
from ..session_content import extract_last_gemini, read_session_json
from ..session_selection import latest_session, scan_latest_session
from ..state import state_payload
from .context import (
    build_cursor,
    current_state_payload,
    reset_for_session_switch,
    update_from_values,
    update_last_gemini,
)
from .waiting import wait_or_timeout


def read_since(reader, state: dict[str, Any], timeout: float, block: bool) -> tuple[str | None, dict[str, Any]]:
    cursor = build_cursor(state, timeout=timeout)

    while True:
        if time.time() - cursor.last_rescan >= cursor.rescan_interval:
            latest = scan_latest_session(reader)
            if latest and latest != reader._preferred_session:
                reader._preferred_session = latest
                reset_for_session_switch(cursor, session=latest)
            cursor.last_rescan = time.time()

        session = latest_session(reader)
        if not session or not session.exists():
            if not block:
                return None, state_payload(
                    session=None,
                    msg_count=0,
                    mtime=0.0,
                    mtime_ns=0,
                    size=0,
                    last_gemini_id=cursor.prev_last_gemini_id,
                    last_gemini_hash=cursor.prev_last_gemini_hash,
                )
            time.sleep(reader._poll_interval)
            if time.time() >= cursor.deadline:
                return None, state
            continue

        try:
            stat = session.stat()
            current_mtime = stat.st_mtime
            current_mtime_ns = getattr(stat, "st_mtime_ns", int(current_mtime * 1_000_000_000))
            current_size = stat.st_size
            if block and current_mtime_ns <= cursor.prev_mtime_ns and current_size == cursor.prev_size:
                if time.time() - cursor.last_forced_read < reader._force_read_interval:
                    result = wait_or_timeout(reader, cursor=cursor, session=session)
                    if result is not None:
                        return result
                    continue

            data = read_session_json(reader, session)
            if data is None:
                raise json.JSONDecodeError("Gemini session JSON is incomplete", "", 0)
            cursor.last_forced_read = time.time()
            messages = data.get("messages", [])
            current_count = len(messages)

            if cursor.unknown_baseline:
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
                if result is not None:
                    return result

                update_from_values(
                    cursor,
                    session=session,
                    current_count=current_count,
                    current_mtime=current_mtime,
                    current_mtime_ns=current_mtime_ns,
                    current_size=current_size,
                )
                update_last_gemini(cursor, data)
                cursor.unknown_baseline = False
                if not block:
                    return None, current_state_payload(cursor, session=session)
                result = wait_or_timeout(reader, cursor=cursor, session=session)
                if result is not None:
                    return result
                continue

            if current_count > cursor.prev_count:
                result = new_message_from_growth(
                    messages[cursor.prev_count:],
                    session=session,
                    current_count=current_count,
                    current_mtime=current_mtime,
                    current_mtime_ns=current_mtime_ns,
                    current_size=current_size,
                    prev_last_gemini_id=cursor.prev_last_gemini_id,
                    prev_last_gemini_hash=cursor.prev_last_gemini_hash,
                )
                if result is not None:
                    return result
            else:
                last = extract_last_gemini(data)
                if last:
                    last_id, content = last
                    if content:
                        current_hash = hash_content(content)
                        if last_id != cursor.prev_last_gemini_id or current_hash != cursor.prev_last_gemini_hash:
                            return content, state_payload(
                                session=session,
                                msg_count=current_count,
                                mtime=current_mtime,
                                mtime_ns=current_mtime_ns,
                                size=current_size,
                                last_gemini_id=last_id,
                                last_gemini_hash=current_hash,
                            )

            update_from_values(
                cursor,
                session=session,
                current_count=current_count,
                current_mtime=current_mtime,
                current_mtime_ns=current_mtime_ns,
                current_size=current_size,
            )
            update_last_gemini(cursor, data)

        except (OSError, json.JSONDecodeError):
            pass

        if not block:
            return None, current_state_payload(cursor, session=session)

        time.sleep(reader._poll_interval)
        if time.time() >= cursor.deadline:
            return None, current_state_payload(cursor, session=session)


__all__ = ["read_since"]
