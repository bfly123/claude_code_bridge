from __future__ import annotations

from typing import Any

from .entries import extract_message


def structured_event(entry: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    entry_type = str(entry.get("type") or "").strip().lower()
    subtype = _optional_text(entry.get("subtype"))
    uuid = _optional_text(entry.get("uuid"), lowercase=False)
    parent_uuid = _optional_text(entry.get("parentUuid"), lowercase=False)

    user_msg = extract_message(entry, "user")
    if user_msg:
        return _event_record(
            role="user",
            text=user_msg,
            entry_type=entry_type,
            subtype=subtype,
            uuid=uuid,
            parent_uuid=parent_uuid,
            stop_reason=None,
            entry=entry,
        )

    assistant_msg = extract_message(entry, "assistant")
    if assistant_msg:
        return _event_record(
            role="assistant",
            text=assistant_msg,
            entry_type=entry_type,
            subtype=subtype,
            uuid=uuid,
            parent_uuid=parent_uuid,
            stop_reason=_assistant_stop_reason(entry),
            entry=entry,
        )

    if entry_type == "system":
        return _event_record(
            role="system",
            text="",
            entry_type=entry_type,
            subtype=subtype,
            uuid=uuid,
            parent_uuid=parent_uuid,
            stop_reason=None,
            entry=entry,
        )
    return None


def _assistant_stop_reason(entry: dict[str, Any]) -> str | None:
    message = entry.get("message")
    if not isinstance(message, dict):
        return None
    return _optional_text(message.get("stop_reason"), lowercase=False)


def _event_record(
    *,
    role: str,
    text: str,
    entry_type: str,
    subtype: str | None,
    uuid: str | None,
    parent_uuid: str | None,
    stop_reason: str | None,
    entry: dict[str, Any],
) -> dict[str, Any]:
    return {
        "role": role,
        "text": text,
        "entry_type": entry_type,
        "subtype": subtype,
        "uuid": uuid,
        "parent_uuid": parent_uuid,
        "stop_reason": stop_reason,
        "entry": entry,
    }


def _optional_text(value: object, *, lowercase: bool = True) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text.lower() if lowercase else text


__all__ = ["structured_event"]
