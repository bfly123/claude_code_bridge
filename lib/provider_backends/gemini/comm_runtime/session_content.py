from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .session_selection import latest_session
from .state import state_payload


def _latest_session_path(reader) -> Path | None:
    session = latest_session(reader)
    if not session or not session.exists():
        return None
    return session


def read_session_json(reader, session: Path) -> dict[str, Any] | None:
    if not session or not session.exists():
        return None
    for attempt in range(10):
        try:
            with session.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            return loaded if isinstance(loaded, dict) else None
        except json.JSONDecodeError:
            if attempt < 9:
                time.sleep(min(reader._poll_interval, 0.05))
            continue
        except OSError:
            return None
    return None


def _payload_messages(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    messages = payload.get("messages", []) if isinstance(payload, dict) else []
    if not isinstance(messages, list):
        return []
    return [msg for msg in messages if isinstance(msg, dict)]


def _message_content(message: dict[str, Any]) -> str:
    content = message.get("content", "")
    if not isinstance(content, str):
        content = str(content)
    return content.strip()


def _last_gemini_message(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    for message in reversed(messages):
        if message.get("type") == "gemini":
            return message
    return None


def last_gemini_details(payload: dict[str, Any]) -> dict[str, Any] | None:
    last = _last_gemini_message(_payload_messages(payload))
    if last is None:
        return None
    tool_calls = last.get("toolCalls")
    thoughts = last.get("thoughts")
    return {
        "id": last.get("id"),
        "content": _message_content(last),
        "tool_call_count": len(tool_calls) if isinstance(tool_calls, list) else 0,
        "thought_count": len(thoughts) if isinstance(thoughts, list) else 0,
    }


def extract_last_gemini(payload: dict[str, Any]) -> tuple[str | None, str] | None:
    details = last_gemini_details(payload)
    if details is None:
        return None
    return details["id"], str(details["content"] or "")


def _session_stats(session: Path | None) -> tuple[float, int, int]:
    if session is None:
        return 0.0, 0, 0
    try:
        stat = session.stat()
    except OSError:
        return 0.0, 0, 0
    mtime = stat.st_mtime
    mtime_ns = getattr(stat, "st_mtime_ns", int(mtime * 1_000_000_000))
    return mtime, mtime_ns, stat.st_size


def _last_gemini_metadata(payload: dict[str, Any] | None) -> tuple[str | None, str | None, int, int]:
    details = last_gemini_details(payload or {})
    if not details:
        return None, None, 0, 0
    last_id = details["id"]
    content = str(details["content"] or "")
    tool_call_count = int(details["tool_call_count"] or 0)
    thought_count = int(details["thought_count"] or 0)
    if not content:
        return last_id, None, tool_call_count, thought_count
    return last_id, hashlib.sha256(content.encode("utf-8")).hexdigest(), tool_call_count, thought_count


def _session_payload(reader) -> tuple[Path | None, dict[str, Any] | None]:
    session = _latest_session_path(reader)
    if session is None:
        return None, None
    return session, read_session_json(reader, session)


def _conversation_pairs(payload: dict[str, Any] | None) -> list[tuple[str, str]]:
    conversations: list[tuple[str, str]] = []
    pending_question: str | None = None
    for message in _payload_messages(payload):
        msg_type = message.get("type")
        content = _message_content(message)
        if msg_type == "user":
            pending_question = content
            continue
        if msg_type == "gemini" and content:
            conversations.append((pending_question or "", content))
            pending_question = None
    return conversations


def _latest_gemini_text(payload: dict[str, Any] | None) -> str | None:
    last = _last_gemini_message(_payload_messages(payload))
    if last is None:
        return None
    content = _message_content(last)
    return content or None


def _state_from_payload(*, session: Path | None, payload: dict[str, Any] | None) -> dict[str, Any]:
    mtime, mtime_ns, size = _session_stats(session)
    msg_count = -1 if session is not None and payload is None else len(_payload_messages(payload))
    last_gemini_id, last_gemini_hash, last_tool_call_count, last_thought_count = _last_gemini_metadata(payload)
    return state_payload(
        session=session,
        msg_count=msg_count,
        mtime=mtime,
        mtime_ns=mtime_ns,
        size=size,
        last_gemini_id=last_gemini_id,
        last_gemini_hash=last_gemini_hash,
        last_tool_call_count=last_tool_call_count,
        last_thought_count=last_thought_count,
    )


def capture_state(reader) -> dict[str, Any]:
    session, payload = _session_payload(reader)
    return _state_from_payload(session=session, payload=payload)


def latest_message(reader) -> str | None:
    _, payload = _session_payload(reader)
    return _latest_gemini_text(payload)


def latest_conversations(reader, n: int = 1) -> list[tuple[str, str]]:
    if int(n) <= 0:
        return []
    _, payload = _session_payload(reader)
    conversations = _conversation_pairs(payload)
    return conversations[-max(1, int(n)) :]


__all__ = [
    "capture_state",
    "extract_last_gemini",
    "last_gemini_details",
    "latest_conversations",
    "latest_message",
    "read_session_json",
]
