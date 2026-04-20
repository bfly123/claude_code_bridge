from __future__ import annotations

from typing import Any

from opencode_runtime.replies import observe_latest_assistant

from .message_reader import read_messages, read_parts
from .session_lookup import coerce_updated, get_latest_session


def _empty_capture_state() -> dict[str, Any]:
    return {
        "session_path": None,
        "session_id": None,
        "session_updated": -1,
        "assistant_count": 0,
        "last_assistant_id": None,
        "last_assistant_parent_id": None,
        "last_assistant_completed": None,
        "last_assistant_req_id": None,
        "last_assistant_text_hash": None,
        "last_assistant_aborted": False,
    }


def _session_payload_state(session_entry: dict[str, Any]) -> tuple[str | None, int]:
    payload = session_entry.get("payload") or {}
    session_id = payload.get("id") if isinstance(payload.get("id"), str) else None
    updated_i = coerce_updated((payload.get("time") or {}).get("updated"))
    return session_id, updated_i


def capture_state(reader) -> dict[str, Any]:
    session_entry = get_latest_session(reader)
    if not session_entry:
        return _empty_capture_state()

    session_id, updated_i = _session_payload_state(session_entry)
    assistant_count = 0
    observed: dict[str, Any] | None = None
    if session_id:
        messages = read_messages(reader, session_id)
        assistant_count = sum(1 for message in messages if message.get("role") == "assistant")
        observed = observe_latest_assistant(
            messages,
            read_parts=lambda message_id: read_parts(reader, message_id),
            extract_req_id_from_text=getattr(reader, "_extract_req_id_from_text", None),
        )

    return {
        "session_path": session_entry.get("path"),
        "session_id": session_id,
        "session_updated": updated_i,
        "assistant_count": assistant_count,
        "last_assistant_id": observed.get("assistant_id") if observed is not None else None,
        "last_assistant_parent_id": observed.get("parent_id") if observed is not None else None,
        "last_assistant_completed": observed.get("completed") if observed is not None else None,
        "last_assistant_req_id": observed.get("req_id") if observed is not None else None,
        "last_assistant_text_hash": observed.get("text_hash") if observed is not None else None,
        "last_assistant_aborted": bool(observed.get("aborted")) if observed is not None else False,
    }


__all__ = ["capture_state"]
