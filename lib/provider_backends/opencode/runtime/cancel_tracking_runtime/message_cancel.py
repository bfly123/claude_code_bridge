from __future__ import annotations

from typing import Any

from opencode_runtime.replies import is_aborted_error

from ..storage_reader import capture_state, read_messages, read_parts


def detect_cancelled_since(reader, state: dict[str, Any], *, req_id: str) -> tuple[bool, dict[str, Any]]:
    normalized_req_id = _normalize_req_id(req_id)
    if not normalized_req_id:
        return False, state

    new_state = capture_state(reader)
    session_id = new_state.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return False, new_state

    assistants = _assistant_messages_with_ids(read_messages(reader, session_id))
    candidates = _candidate_cancel_messages(
        assistants,
        prev_count=_coerce_int(state.get("assistant_count")),
        prev_last=state.get("last_assistant_id"),
        prev_completed=state.get("last_assistant_completed"),
        new_state=new_state,
    )
    if not candidates:
        return False, new_state

    for message in candidates:
        if not _message_matches_req_id(reader, message, req_id=normalized_req_id):
            continue
        return True, new_state
    return False, new_state


def _message_matches_req_id(reader, message: dict[str, Any], *, req_id: str) -> bool:
    if not is_aborted_error(message.get("error")):
        return False
    parent_id = message.get("parentID")
    if not isinstance(parent_id, str) or not parent_id:
        return False
    parts = read_parts(reader, parent_id)
    prompt_text = reader._extract_text(parts, allow_reasoning_fallback=True)
    prompt_req_id = reader._extract_req_id_from_text(prompt_text)
    return bool(prompt_req_id and prompt_req_id == req_id)


def _assistant_messages_with_ids(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        message
        for message in messages
        if message.get("role") == "assistant" and isinstance(message.get("id"), str)
    ]


def _candidate_cancel_messages(
    assistants: list[dict[str, Any]],
    *,
    prev_count: int,
    prev_last: object,
    prev_completed: object,
    new_state: dict[str, Any],
) -> list[dict[str, Any]]:
    by_id = {str(message["id"]): message for message in assistants}
    candidates: list[dict[str, Any]] = []
    if prev_count < len(assistants):
        candidates.extend(assistants[prev_count:])

    last_id = new_state.get("last_assistant_id")
    _append_by_id(candidates, by_id, last_id)
    if prev_last != last_id:
        _append_by_id(candidates, by_id, prev_last)
    elif new_state.get("last_assistant_completed") != prev_completed:
        _append_by_id(candidates, by_id, prev_last)
    return candidates


def _append_by_id(candidates: list[dict[str, Any]], by_id: dict[str, dict[str, Any]], message_id: object) -> None:
    if not isinstance(message_id, str):
        return
    message = by_id.get(message_id)
    if message is not None and message not in candidates:
        candidates.append(message)


def _normalize_req_id(req_id: object) -> str:
    return str(req_id or "").strip().lower()


def _coerce_int(value: object) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


__all__ = ["detect_cancelled_since"]
