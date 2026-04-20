from __future__ import annotations

import hashlib
from typing import Callable

from .errors import is_aborted_error
from .extraction import extract_text


def find_new_assistant_reply_with_state(
    messages: list[dict],
    state: dict,
    *,
    read_parts: Callable[[str], list[dict]],
    extract_req_id_from_text: Callable[[str], str | None] | None = None,
) -> tuple[str | None, dict | None]:
    previous = _assistant_state(state)
    observed = observe_latest_assistant(
        messages,
        read_parts=read_parts,
        extract_req_id_from_text=extract_req_id_from_text,
    )
    if observed is None:
        return None, None

    assistants = _assistant_messages(messages)
    if not _assistant_state_changed(previous, observed=observed, assistant_count=len(assistants)):
        return None, None
    reply_state = {
        'assistant_count': len(assistants),
        'last_assistant_id': observed['assistant_id'],
        'last_assistant_parent_id': observed['parent_id'],
        'last_assistant_completed': observed['completed'],
        'last_assistant_req_id': observed['req_id'],
        'last_assistant_text_hash': observed['text_hash'],
        'last_assistant_aborted': observed['aborted'],
    }
    reply = observed["text"] or None
    return reply, reply_state


def observe_latest_assistant(
    messages: list[dict],
    *,
    read_parts: Callable[[str], list[dict]],
    extract_req_id_from_text: Callable[[str], str | None] | None = None,
) -> dict[str, object] | None:
    assistants = _assistant_messages(messages)
    if not assistants:
        return None
    latest = assistants[-1]
    return _observed_assistant_reply(
        latest,
        read_parts=read_parts,
        extract_req_id_from_text=extract_req_id_from_text,
    )


def latest_message_from_messages(
    messages: list[dict],
    *,
    read_parts: Callable[[str], list[dict]],
) -> str | None:
    observed = observe_latest_assistant(messages, read_parts=read_parts)
    if observed is None or observed.get('completed') is None:
        return None
    text = str(observed.get('text') or '')
    return text or None


def _assistant_messages(messages: list[dict]) -> list[dict]:
    return [
        message
        for message in messages
        if message.get('role') == 'assistant' and isinstance(message.get('id'), str)
    ]


def _assistant_state(state: dict) -> dict[str, object]:
    return {
        'assistant_count': int(state.get('assistant_count') or 0),
        'assistant_id': state.get('last_assistant_id'),
        'parent_id': state.get('last_assistant_parent_id'),
        'completed': state.get('last_assistant_completed'),
        'req_id': state.get('last_assistant_req_id'),
        'text_hash': state.get('last_assistant_text_hash'),
        'aborted': bool(state.get('last_assistant_aborted')),
    }


def _observed_assistant_reply(
    latest: dict,
    *,
    read_parts: Callable[[str], list[dict]],
    extract_req_id_from_text: Callable[[str], str | None] | None = None,
) -> dict[str, object] | None:
    assistant_id = str(latest.get('id'))
    completed = _completed_marker(latest)
    text = _assistant_text(assistant_id, read_parts, allow_reasoning_fallback=False)
    parent_id = _parent_message_id(latest)
    req_id = _parent_req_id(
        parent_id,
        read_parts=read_parts,
        extract_req_id_from_text=extract_req_id_from_text,
    )
    return {
        'assistant_id': assistant_id,
        'parent_id': parent_id,
        'completed': completed,
        'text': text,
        'req_id': req_id,
        'text_hash': _text_hash(text),
        'aborted': is_aborted_error(latest.get('error')),
    }


def _assistant_text(
    assistant_id: str,
    read_parts: Callable[[str], list[dict]],
    *,
    allow_reasoning_fallback: bool,
) -> str:
    parts = read_parts(assistant_id)
    return extract_text(parts, allow_reasoning_fallback=allow_reasoning_fallback)


def _parent_message_id(message: dict) -> str | None:
    parent_id = message.get('parentID')
    if isinstance(parent_id, str) and parent_id:
        return parent_id
    parent_id = message.get('parent_id')
    if isinstance(parent_id, str) and parent_id:
        return parent_id
    return None


def _parent_req_id(
    parent_id: str | None,
    *,
    read_parts: Callable[[str], list[dict]],
    extract_req_id_from_text: Callable[[str], str | None] | None,
) -> str | None:
    if not parent_id or extract_req_id_from_text is None:
        return None
    prompt_text = _assistant_text(parent_id, read_parts, allow_reasoning_fallback=True)
    req_id = extract_req_id_from_text(prompt_text)
    if not isinstance(req_id, str):
        return None
    normalized = req_id.strip().lower()
    return normalized or None


def _text_hash(text: str) -> str | None:
    normalized = str(text or '').strip()
    if not normalized:
        return None
    return hashlib.sha1(normalized.encode('utf-8')).hexdigest()


def _assistant_state_changed(
    previous: dict[str, object],
    *,
    observed: dict[str, object],
    assistant_count: int,
) -> bool:
    return (
        assistant_count > int(previous['assistant_count'])
        or observed['assistant_id'] != previous['assistant_id']
        or observed['parent_id'] != previous['parent_id']
        or observed['completed'] != previous['completed']
        or observed['req_id'] != previous['req_id']
        or observed['text_hash'] != previous['text_hash']
        or observed['aborted'] != previous['aborted']
    )


def _completed_marker(message: dict) -> int | None:
    completed = (message.get('time') or {}).get('completed')
    try:
        return int(completed) if completed is not None else None
    except Exception:
        return None

__all__ = ['find_new_assistant_reply_with_state', 'latest_message_from_messages', 'observe_latest_assistant']
