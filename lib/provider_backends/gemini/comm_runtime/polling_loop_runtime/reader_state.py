from __future__ import annotations

import time

from ..session_selection import scan_latest_session
from ..state import state_payload
from .context import reset_for_session_switch


def refresh_latest_session(reader, cursor) -> None:
    if time.time() - cursor.last_rescan < cursor.rescan_interval:
        return
    latest = scan_latest_session(reader)
    if latest and latest != reader._preferred_session:
        reader._preferred_session = latest
        reset_for_session_switch(cursor, session=latest)
    cursor.last_rescan = time.time()


def missing_session_state(cursor) -> dict[str, object]:
    return state_payload(
        session=None,
        msg_count=0,
        mtime=0.0,
        mtime_ns=0,
        size=0,
        last_gemini_id=cursor.prev_last_gemini_id,
        last_gemini_hash=cursor.prev_last_gemini_hash,
        last_tool_call_count=cursor.prev_last_tool_call_count,
        last_thought_count=cursor.prev_last_thought_count,
    )


def session_stat_values(session) -> tuple[float, int, int]:
    stat = session.stat()
    current_mtime = stat.st_mtime
    current_mtime_ns = getattr(stat, "st_mtime_ns", int(current_mtime * 1_000_000_000))
    return current_mtime, current_mtime_ns, stat.st_size


def should_wait_for_forced_read(
    reader,
    cursor,
    *,
    current_mtime_ns: int,
    current_size: int,
    block: bool,
) -> bool:
    return (
        block
        and current_mtime_ns <= cursor.prev_mtime_ns
        and current_size == cursor.prev_size
        and time.time() - cursor.last_forced_read < reader._force_read_interval
    )


def gemini_reply_changed(cursor, *, last_id: str | None, current_hash: str) -> bool:
    return last_id != cursor.prev_last_gemini_id or current_hash != cursor.prev_last_gemini_hash


def reply_state_payload(
    *,
    session,
    current_count: int,
    current_mtime: float,
    current_mtime_ns: int,
    current_size: int,
    last_id: str | None,
    current_hash: str,
    last_tool_call_count: int = 0,
    last_thought_count: int = 0,
) -> dict[str, object]:
    return state_payload(
        session=session,
        msg_count=current_count,
        mtime=current_mtime,
        mtime_ns=current_mtime_ns,
        size=current_size,
        last_gemini_id=last_id,
        last_gemini_hash=current_hash,
        last_tool_call_count=last_tool_call_count,
        last_thought_count=last_thought_count,
    )


__all__ = [
    "gemini_reply_changed",
    "missing_session_state",
    "refresh_latest_session",
    "reply_state_payload",
    "session_stat_values",
    "should_wait_for_forced_read",
]
