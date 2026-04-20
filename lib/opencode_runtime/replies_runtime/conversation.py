from __future__ import annotations

from typing import Callable

from .extraction import extract_text


def conversations_from_messages(
    messages: list[dict],
    *,
    read_parts: Callable[[str], list[dict]],
    n: int = 1,
) -> list[tuple[str, str]]:
    conversations: list[tuple[str, str]] = []
    pending_question: str | None = None

    for message in messages:
        message_id = message.get('id')
        if not isinstance(message_id, str) or not message_id:
            continue
        text = extract_text(read_parts(message_id))
        role = message.get('role')
        if role == 'user':
            pending_question = text
            continue
        if role == 'assistant' and text:
            conversations.append((pending_question or '', text))
            pending_question = None

    if n <= 0:
        return conversations
    return conversations[-n:] if len(conversations) > n else conversations


__all__ = ['conversations_from_messages']
