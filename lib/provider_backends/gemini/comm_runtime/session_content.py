from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .session_selection import latest_session
from .state import state_payload


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


def extract_last_gemini(payload: dict[str, Any]) -> tuple[str | None, str] | None:
    messages = payload.get("messages", []) if isinstance(payload, dict) else []
    if not isinstance(messages, list):
        return None
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        if msg.get("type") != "gemini":
            continue
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        return msg.get("id"), content.strip()
    return None


def capture_state(reader) -> dict[str, Any]:
    session = latest_session(reader)
    msg_count = 0
    mtime = 0.0
    mtime_ns = 0
    size = 0
    last_gemini_id: str | None = None
    last_gemini_hash: str | None = None
    if session and session.exists():
        data: dict[str, Any] | None = None
        try:
            stat = session.stat()
            mtime = stat.st_mtime
            mtime_ns = getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))
            size = stat.st_size
        except OSError:
            pass

        data = read_session_json(reader, session)

        if data is None:
            msg_count = -1
        else:
            msg_count = len(data.get("messages", []))
            last = extract_last_gemini(data)
            if last:
                last_gemini_id, content = last
                last_gemini_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return state_payload(
        session=session,
        msg_count=msg_count,
        mtime=mtime,
        mtime_ns=mtime_ns,
        size=size,
        last_gemini_id=last_gemini_id,
        last_gemini_hash=last_gemini_hash,
    )


def latest_message(reader) -> str | None:
    session = latest_session(reader)
    if not session or not session.exists():
        return None
    try:
        data = read_session_json(reader, session)
        if not isinstance(data, dict):
            return None
        messages = data.get("messages", [])
        for msg in reversed(messages):
            if msg.get("type") == "gemini":
                return str(msg.get("content", "")).strip()
    except (OSError, json.JSONDecodeError):
        pass
    return None


def latest_conversations(reader, n: int = 1) -> list[tuple[str, str]]:
    session = latest_session(reader)
    if not session or not session.exists():
        return []
    try:
        data = read_session_json(reader, session)
        if not isinstance(data, dict):
            return []
        messages = data.get("messages", [])
    except (OSError, json.JSONDecodeError):
        return []

    conversations: list[tuple[str, str]] = []
    pending_question: str | None = None

    for msg in messages:
        msg_type = msg.get("type")
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        content = content.strip()

        if msg_type == "user":
            pending_question = content
        elif msg_type == "gemini" and content:
            question = pending_question or ""
            conversations.append((question, content))
            pending_question = None

    return conversations[-n:] if len(conversations) > n else conversations


__all__ = [
    "capture_state",
    "extract_last_gemini",
    "latest_conversations",
    "latest_message",
    "read_session_json",
]
