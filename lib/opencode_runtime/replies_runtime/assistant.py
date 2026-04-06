from __future__ import annotations

from typing import Callable

from .extraction import extract_text


def find_new_assistant_reply_with_state(
    messages: list[dict],
    state: dict,
    *,
    read_parts: Callable[[str], list[dict]],
    completion_marker: str,
) -> tuple[str | None, dict | None]:
    previous = _assistant_state(state)
    assistants = _assistant_messages(messages)
    if not assistants:
        return None, None

    latest = assistants[-1]
    observed = _observed_assistant_reply(
        latest,
        read_parts=read_parts,
        completion_marker=completion_marker,
    )
    if observed is None:
        return None, None
    if not _assistant_state_changed(previous, observed=observed, assistant_count=len(assistants)):
        return None, None
    return observed["text"] or None, {
        'assistant_count': len(assistants),
        'last_assistant_id': observed['assistant_id'],
        'last_assistant_completed': observed['completed'],
        'last_assistant_has_done': observed['has_done'],
    }


def latest_message_from_messages(
    messages: list[dict],
    *,
    read_parts: Callable[[str], list[dict]],
) -> str | None:
    assistants = _assistant_messages(messages)
    if not assistants:
        return None
    latest = assistants[-1]
    if (latest.get('time') or {}).get('completed') is None:
        return None
    text = _assistant_text(str(latest.get('id')), read_parts, allow_reasoning_fallback=False)
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
        'completed': state.get('last_assistant_completed'),
        'has_done': bool(state.get('last_assistant_has_done')),
    }


def _observed_assistant_reply(
    latest: dict,
    *,
    read_parts: Callable[[str], list[dict]],
    completion_marker: str,
) -> dict[str, object] | None:
    assistant_id = str(latest.get('id'))
    completed = _completed_marker(latest)
    text = _assistant_text(assistant_id, read_parts, allow_reasoning_fallback=True)
    has_done = _has_done_marker(text)
    if completed is None and not _has_completion_marker(text, completion_marker, has_done=has_done):
        return None
    return {
        'assistant_id': assistant_id,
        'completed': completed if completed is not None else 0,
        'text': text,
        'has_done': has_done,
    }


def _assistant_text(
    assistant_id: str,
    read_parts: Callable[[str], list[dict]],
    *,
    allow_reasoning_fallback: bool,
) -> str:
    parts = read_parts(assistant_id)
    return extract_text(parts, allow_reasoning_fallback=allow_reasoning_fallback)


def _has_done_marker(text: str) -> bool:
    return bool(text) and 'CCB_DONE:' in text


def _has_completion_marker(text: str, completion_marker: str, *, has_done: bool) -> bool:
    return bool(text) and (completion_marker in text or has_done)


def _assistant_state_changed(
    previous: dict[str, object],
    *,
    observed: dict[str, object],
    assistant_count: int,
) -> bool:
    return (
        assistant_count > int(previous['assistant_count'])
        or observed['assistant_id'] != previous['assistant_id']
        or observed['completed'] != previous['completed']
        or observed['has_done'] != previous['has_done']
    )


def _completed_marker(message: dict) -> int | None:
    completed = (message.get('time') or {}).get('completed')
    try:
        return int(completed) if completed is not None else None
    except Exception:
        return None


__all__ = ['find_new_assistant_reply_with_state', 'latest_message_from_messages']
