from __future__ import annotations

from opencode_runtime.replies import conversations_from_messages, latest_message_from_messages

from .storage_reader import get_latest_session, read_messages, read_parts


def latest_message(reader) -> str | None:
    session_id = _latest_session_id(reader)
    if not session_id:
        return None
    messages = read_messages(reader, session_id)
    return latest_message_from_messages(messages, read_parts=lambda message_id: read_parts(reader, message_id))


def conversations_for_session(reader, session_id: str, n: int = 1) -> list[tuple[str, str]]:
    if not isinstance(session_id, str) or not session_id:
        return []
    messages = read_messages(reader, session_id)
    return conversations_from_messages(messages, read_parts=lambda message_id: read_parts(reader, message_id), n=n)


def latest_conversations(reader, n: int = 1) -> list[tuple[str, str]]:
    session_id = _latest_session_id(reader)
    if not session_id:
        return []
    messages = read_messages(reader, session_id)
    return conversations_from_messages(messages, read_parts=lambda message_id: read_parts(reader, message_id), n=n)


def _latest_session_id(reader) -> str | None:
    session_entry = get_latest_session(reader)
    if not session_entry:
        return None
    payload = session_entry.get("payload") or {}
    session_id = payload.get("id")
    if not isinstance(session_id, str) or not session_id:
        return None
    return session_id


__all__ = ["conversations_for_session", "latest_conversations", "latest_message"]
