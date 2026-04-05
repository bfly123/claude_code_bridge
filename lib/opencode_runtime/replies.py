from __future__ import annotations

from typing import Callable


def extract_text(parts: list[dict], allow_reasoning_fallback: bool = True) -> str:
    def _collect(types: set[str]) -> str:
        out: list[str] = []
        for part in parts:
            if part.get("type") not in types:
                continue
            text = part.get("text")
            if isinstance(text, str) and text:
                out.append(text)
        return "".join(out).strip()

    text = _collect({"text"})
    if text:
        return text
    if allow_reasoning_fallback:
        return _collect({"reasoning"})
    return ""


def find_new_assistant_reply_with_state(
    messages: list[dict],
    state: dict,
    *,
    read_parts: Callable[[str], list[dict]],
    completion_marker: str,
) -> tuple[str | None, dict | None]:
    prev_count = int(state.get("assistant_count") or 0)
    prev_last = state.get("last_assistant_id")
    prev_completed = state.get("last_assistant_completed")
    prev_has_done = bool(state.get("last_assistant_has_done"))

    assistants = [message for message in messages if message.get("role") == "assistant" and isinstance(message.get("id"), str)]
    if not assistants:
        return None, None

    latest = assistants[-1]
    latest_id = latest.get("id")
    completed = (latest.get("time") or {}).get("completed")
    try:
        completed_i = int(completed) if completed is not None else None
    except Exception:
        completed_i = None

    parts: list[dict] | None = None
    text = ""
    has_done = False

    if completed_i is None:
        parts = read_parts(str(latest_id))
        text = extract_text(parts, allow_reasoning_fallback=True)
        has_done = bool(text) and ("CCB_DONE:" in text)
        if text and (completion_marker in text or has_done):
            completed_i = 0
        else:
            return None, None

    if parts is None:
        parts = read_parts(str(latest_id))
        text = extract_text(parts, allow_reasoning_fallback=True)
        has_done = bool(text) and ("CCB_DONE:" in text)

    if (
        len(assistants) <= prev_count
        and latest_id == prev_last
        and completed_i == prev_completed
        and has_done == prev_has_done
    ):
        return None, None

    return text or None, {
        "assistant_count": len(assistants),
        "last_assistant_id": latest_id,
        "last_assistant_completed": completed_i,
        "last_assistant_has_done": has_done,
    }


def latest_message_from_messages(messages: list[dict], *, read_parts: Callable[[str], list[dict]]) -> str | None:
    assistants = [message for message in messages if message.get("role") == "assistant" and isinstance(message.get("id"), str)]
    if not assistants:
        return None
    latest = assistants[-1]
    completed = (latest.get("time") or {}).get("completed")
    if completed is None:
        return None
    parts = read_parts(str(latest.get("id")))
    text = extract_text(parts)
    return text or None


def conversations_from_messages(
    messages: list[dict],
    *,
    read_parts: Callable[[str], list[dict]],
    n: int = 1,
) -> list[tuple[str, str]]:
    conversations: list[tuple[str, str]] = []
    pending_question: str | None = None

    for message in messages:
        role = message.get("role")
        message_id = message.get("id")
        if not isinstance(message_id, str) or not message_id:
            continue
        parts = read_parts(message_id)
        text = extract_text(parts)
        if role == "user":
            pending_question = text
            continue
        if role == "assistant" and text:
            conversations.append((pending_question or "", text))
            pending_question = None

    if n <= 0:
        return conversations
    return conversations[-n:] if len(conversations) > n else conversations


def is_aborted_error(error_obj: object) -> bool:
    if not isinstance(error_obj, dict):
        return False
    name = error_obj.get("name")
    if isinstance(name, str) and "aborted" in name.lower():
        return True
    data = error_obj.get("data")
    if isinstance(data, dict):
        message = data.get("message")
        if isinstance(message, str) and ("aborted" in message.lower() or "cancel" in message.lower()):
            return True
    return False


def extract_req_id_from_text(text: str, req_id_re) -> str | None:
    if not text:
        return None
    match = req_id_re.search(text)
    return match.group(1).lower() if match else None
