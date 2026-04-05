from __future__ import annotations

import os
import time
from typing import Any

from opencode_runtime.replies import find_new_assistant_reply_with_state

from .storage_reader import get_latest_session, read_messages, read_parts


def find_new_assistant_reply_with_reader_state(
    reader,
    session_id: str,
    state: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    messages = read_messages(reader, session_id)
    completion_marker = (os.environ.get("CCB_EXECUTION_COMPLETE_MARKER") or "[EXECUTION_COMPLETE]").strip()
    if not completion_marker:
        completion_marker = "[EXECUTION_COMPLETE]"
    reply, reply_state = find_new_assistant_reply_with_state(
        messages,
        state,
        read_parts=lambda message_id: read_parts(reader, message_id),
        completion_marker=completion_marker,
    )
    if reply_state and reply_state.get("last_assistant_completed") == 0:
        reply_state["last_assistant_completed"] = int(time.time() * 1000)
    return reply, reply_state


def read_since(reader, state: dict[str, Any], timeout: float, block: bool) -> tuple[str | None, dict[str, Any]]:
    deadline = time.time() + timeout
    last_forced_read = time.time()

    session_id = state.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        session_id = None

    while True:
        session_entry = get_latest_session(reader)
        if not session_entry:
            if not block:
                return None, state
            time.sleep(reader._poll_interval)
            if time.time() >= deadline:
                return None, state
            continue

        payload = session_entry.get("payload") or {}
        current_session_id = payload.get("id") if isinstance(payload.get("id"), str) else None
        if session_id and current_session_id and current_session_id != session_id:
            session_id = current_session_id
            state = _reset_state_for_session(state, current_session_id)
        elif not session_id:
            session_id = current_session_id

        if not current_session_id:
            if not block:
                return None, state
            time.sleep(reader._poll_interval)
            if time.time() >= deadline:
                return None, state
            continue

        updated_i = _session_updated(payload)
        prev_updated = int(state.get("session_updated") or -1)
        should_scan = updated_i != prev_updated
        if block and not should_scan and (time.time() - last_forced_read) >= reader._force_read_interval:
            should_scan = True
            last_forced_read = time.time()

        if should_scan:
            reply, reply_state = find_new_assistant_reply_with_reader_state(reader, current_session_id, state)
            if reply:
                return reply, _merge_reply_state(
                    state,
                    session_entry=session_entry,
                    current_session_id=current_session_id,
                    updated_i=updated_i,
                    reply_state=reply_state,
                )

            state = _refresh_observed_state(reader, state, current_session_id, updated_i=updated_i)

        if not block:
            return None, state

        time.sleep(reader._poll_interval)
        if time.time() >= deadline:
            return None, state


def _session_updated(payload: dict[str, Any]) -> int:
    updated = (payload.get("time") or {}).get("updated")
    try:
        return int(updated)
    except Exception:
        return -1


def _reset_state_for_session(state: dict[str, Any], session_id: str) -> dict[str, Any]:
    new_state = dict(state)
    new_state["session_id"] = session_id
    new_state["session_updated"] = -1
    new_state["assistant_count"] = 0
    new_state["last_assistant_id"] = None
    new_state["last_assistant_completed"] = None
    new_state["last_assistant_has_done"] = False
    return new_state


def _merge_reply_state(
    state: dict[str, Any],
    *,
    session_entry: dict[str, Any],
    current_session_id: str,
    updated_i: int,
    reply_state: dict[str, Any] | None,
) -> dict[str, Any]:
    new_state = dict(state)
    new_state["session_id"] = current_session_id
    new_state["session_updated"] = updated_i
    if (session_entry.get("payload") or {}).get("id") == current_session_id:
        new_state["session_path"] = session_entry.get("path")
    if reply_state:
        new_state.update(reply_state)
    return new_state


def _refresh_observed_state(reader, state: dict[str, Any], session_id: str, *, updated_i: int) -> dict[str, Any]:
    new_state = dict(state)
    new_state["session_id"] = session_id
    new_state["session_updated"] = updated_i
    try:
        current_messages = read_messages(reader, session_id)
        assistants = [
            message
            for message in current_messages
            if message.get("role") == "assistant" and isinstance(message.get("id"), str)
        ]
        new_state["assistant_count"] = len(assistants)
        if assistants:
            latest = assistants[-1]
            new_state["last_assistant_id"] = latest.get("id")
            completed = (latest.get("time") or {}).get("completed")
            try:
                new_state["last_assistant_completed"] = int(completed) if completed is not None else None
            except Exception:
                new_state["last_assistant_completed"] = None
            parts = read_parts(reader, str(latest.get("id")))
            text = reader._extract_text(parts, allow_reasoning_fallback=True)
            new_state["last_assistant_has_done"] = bool(text) and ("CCB_DONE:" in text)
    except Exception:
        pass
    return new_state


__all__ = ["find_new_assistant_reply_with_reader_state", "read_since"]
