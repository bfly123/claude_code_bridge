from __future__ import annotations

from typing import Any

from .message_reader import read_messages, read_parts
from .session_lookup import coerce_updated, get_latest_session


def capture_state(reader) -> dict[str, Any]:
    session_entry = get_latest_session(reader)
    if not session_entry:
        return {
            "session_path": None,
            "session_id": None,
            "session_updated": -1,
            "assistant_count": 0,
            "last_assistant_id": None,
            "last_assistant_completed": None,
            "last_assistant_has_done": False,
        }

    payload = session_entry.get("payload") or {}
    session_id = payload.get("id") if isinstance(payload.get("id"), str) else None
    updated_i = coerce_updated((payload.get("time") or {}).get("updated"))

    assistant_count = 0
    last_assistant_id: str | None = None
    last_completed: int | None = None
    last_has_done = False

    if session_id:
        messages = read_messages(reader, session_id)
        for msg in messages:
            if msg.get("role") == "assistant":
                assistant_count += 1
                mid = msg.get("id")
                if isinstance(mid, str):
                    last_assistant_id = mid
                    completed = (msg.get("time") or {}).get("completed")
                    try:
                        last_completed = int(completed) if completed is not None else None
                    except Exception:
                        last_completed = None
        if isinstance(last_assistant_id, str) and last_assistant_id:
            parts = read_parts(reader, last_assistant_id)
            text = reader._extract_text(parts, allow_reasoning_fallback=True)
            last_has_done = bool(text) and ("CCB_DONE:" in text)

    return {
        "session_path": session_entry.get("path"),
        "session_id": session_id,
        "session_updated": updated_i,
        "assistant_count": assistant_count,
        "last_assistant_id": last_assistant_id,
        "last_assistant_completed": last_completed,
        "last_assistant_has_done": last_has_done,
    }


__all__ = ["capture_state"]
