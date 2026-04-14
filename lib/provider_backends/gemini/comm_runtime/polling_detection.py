from __future__ import annotations

import hashlib
from typing import Any

from .session_content import last_gemini_details
from .state import state_payload


def handle_unknown_baseline(
    data: dict[str, Any],
    *,
    session,
    current_count: int,
    current_mtime: float,
    current_mtime_ns: int,
    current_size: int,
    prev_mtime_ns: int,
    prev_size: int,
):
    messages = data.get("messages", [])
    last_msg = messages[-1] if messages else None
    if isinstance(last_msg, dict):
        last_type = last_msg.get("type")
        last_content = (last_msg.get("content") or "").strip()
    else:
        last_type = None
        last_content = ""

    if last_type == "gemini" and last_content and (current_mtime_ns > prev_mtime_ns or current_size != prev_size):
        msg_id = last_msg.get("id") if isinstance(last_msg, dict) else None
        content_hash = hash_content(last_content)
        details = last_gemini_details({"messages": [last_msg]}) if isinstance(last_msg, dict) else None
        return last_content, state_payload(
            session=session,
            msg_count=current_count,
            mtime=current_mtime,
            mtime_ns=current_mtime_ns,
            size=current_size,
            last_gemini_id=msg_id,
            last_gemini_hash=content_hash,
            last_tool_call_count=(details or {}).get("tool_call_count", 0),
            last_thought_count=(details or {}).get("thought_count", 0),
        )
    return None


def new_message_from_growth(
    new_messages: list[dict[str, Any]],
    *,
    session,
    current_count: int,
    current_mtime: float,
    current_mtime_ns: int,
    current_size: int,
    prev_last_gemini_id: str | None,
    prev_last_gemini_hash: str | None,
):
    last_gemini_content = None
    last_gemini_id = None
    last_gemini_hash = None
    last_tool_call_count = 0
    last_thought_count = 0
    for msg in new_messages:
        if msg.get("type") == "gemini":
            content = str(msg.get("content", "")).strip()
            if content:
                content_hash = hash_content(content)
                msg_id = msg.get("id")
                if msg_id and msg_id == prev_last_gemini_id and content_hash == prev_last_gemini_hash:
                    continue
                details = last_gemini_details({"messages": [msg]})
                last_gemini_content = content
                last_gemini_id = msg_id
                last_gemini_hash = content_hash
                last_tool_call_count = int((details or {}).get("tool_call_count", 0) or 0)
                last_thought_count = int((details or {}).get("thought_count", 0) or 0)
    if not last_gemini_content:
        return None
    return last_gemini_content, state_payload(
        session=session,
        msg_count=current_count,
        mtime=current_mtime,
        mtime_ns=current_mtime_ns,
        size=current_size,
        last_gemini_id=last_gemini_id,
        last_gemini_hash=last_gemini_hash,
        last_tool_call_count=last_tool_call_count,
        last_thought_count=last_thought_count,
    )


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


__all__ = ["handle_unknown_baseline", "hash_content", "new_message_from_growth"]
