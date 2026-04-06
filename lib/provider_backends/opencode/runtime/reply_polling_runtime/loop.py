from __future__ import annotations

import time
from typing import Any, Callable


def read_since(
    reader,
    state: dict[str, Any],
    timeout: float,
    block: bool,
    *,
    get_latest_session_fn: Callable,
    find_reply_fn: Callable,
    merge_reply_state_fn: Callable,
    refresh_observed_state_fn: Callable,
    reset_state_for_session_fn: Callable,
    session_updated_fn: Callable,
) -> tuple[str | None, dict[str, Any]]:
    deadline = time.time() + timeout
    last_forced_read = time.time()
    session_id = state_session_id(state)

    while True:
        session_entry = get_latest_session_fn(reader)
        if not session_entry:
            if should_return_without_session(block):
                return None, state
            if sleep_or_timeout(reader, deadline):
                return None, state
            continue

        current_session_id = payload_session_id(session_entry)
        session_id, state = advance_session_state(
            state,
            session_id=session_id,
            current_session_id=current_session_id,
            reset_state_for_session_fn=reset_state_for_session_fn,
        )

        if not current_session_id:
            if should_return_without_session(block):
                return None, state
            if sleep_or_timeout(reader, deadline):
                return None, state
            continue

        updated_i = session_updated_fn(session_entry.get("payload") or {})
        prev_updated = int(state.get("session_updated") or -1)
        if should_scan_session(
            block=block,
            updated_i=updated_i,
            prev_updated=prev_updated,
            last_forced_read=last_forced_read,
            force_read_interval=reader._force_read_interval,
        ):
            last_forced_read, reply, state = scan_current_session(
                reader,
                state,
                current_session_id=current_session_id,
                session_entry=session_entry,
                updated_i=updated_i,
                prev_updated=prev_updated,
                block=block,
                last_forced_read=last_forced_read,
                find_reply_fn=find_reply_fn,
                merge_reply_state_fn=merge_reply_state_fn,
                refresh_observed_state_fn=refresh_observed_state_fn,
            )
            if reply:
                return reply, state

        if not block:
            return None, state
        if sleep_or_timeout(reader, deadline):
            return None, state


def state_session_id(state: dict[str, Any]) -> str | None:
    session_id = state.get("session_id")
    if isinstance(session_id, str) and session_id:
        return session_id
    return None


def payload_session_id(session_entry: dict[str, Any]) -> str | None:
    payload = session_entry.get("payload") or {}
    session_id = payload.get("id")
    return session_id if isinstance(session_id, str) else None


def should_return_without_session(block: bool) -> bool:
    return not block


def advance_session_state(
    state: dict[str, Any],
    *,
    session_id: str | None,
    current_session_id: str | None,
    reset_state_for_session_fn: Callable,
) -> tuple[str | None, dict[str, Any]]:
    if session_id and current_session_id and current_session_id != session_id:
        return current_session_id, reset_state_for_session_fn(state, current_session_id)
    if not session_id:
        return current_session_id, state
    return session_id, state


def should_scan_session(
    *,
    block: bool,
    updated_i: int,
    prev_updated: int,
    last_forced_read: float,
    force_read_interval: float,
) -> bool:
    if updated_i != prev_updated:
        return True
    return block and (time.time() - last_forced_read) >= force_read_interval


def scan_current_session(
    reader,
    state: dict[str, Any],
    *,
    current_session_id: str,
    session_entry: dict[str, Any],
    updated_i: int,
    prev_updated: int,
    block: bool,
    last_forced_read: float,
    find_reply_fn: Callable,
    merge_reply_state_fn: Callable,
    refresh_observed_state_fn: Callable,
) -> tuple[float, str | None, dict[str, Any]]:
    if block and updated_i == prev_updated:
        last_forced_read = time.time()
    reply, reply_state = find_reply_fn(reader, current_session_id, state)
    if reply:
        merged_state = merge_reply_state_fn(
            state,
            session_entry=session_entry,
            current_session_id=current_session_id,
            updated_i=updated_i,
            reply_state=reply_state,
        )
        return last_forced_read, reply, merged_state
    refreshed = refresh_observed_state_fn(
        reader,
        state,
        current_session_id,
        updated_i=updated_i,
    )
    return last_forced_read, None, refreshed


def sleep_or_timeout(reader, deadline: float) -> bool:
    time.sleep(reader._poll_interval)
    return time.time() >= deadline


__all__ = [
    "advance_session_state",
    "payload_session_id",
    "read_since",
    "scan_current_session",
    "should_scan_session",
    "sleep_or_timeout",
    "state_session_id",
]
