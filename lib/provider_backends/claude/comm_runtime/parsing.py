from __future__ import annotations

from typing import Any, Optional


def extract_content_text(content: Any) -> Optional[str]:
    if content is None:
        return None
    if isinstance(content, str):
        return content.strip() or None
    if not isinstance(content, list):
        return None
    texts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").strip().lower()
        if item_type in ("thinking", "thinking_delta"):
            continue
        text = item.get("text")
        if not text and item_type == "text":
            text = item.get("content")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
    if not texts:
        return None
    return "\n".join(texts).strip()


def extract_message(entry: dict, role: str) -> Optional[str]:
    if not isinstance(entry, dict):
        return None
    entry_type = (entry.get("type") or "").strip().lower()

    if entry_type == "response_item":
        payload = entry.get("payload", {})
        if not isinstance(payload, dict) or payload.get("type") != "message":
            return None
        if (payload.get("role") or "").lower() != role:
            return None
        return extract_content_text(payload.get("content"))

    if entry_type == "event_msg":
        payload = entry.get("payload", {})
        if not isinstance(payload, dict):
            return None
        payload_type = (payload.get("type") or "").lower()
        if payload_type in ("agent_message", "assistant_message", "assistant"):
            if (payload.get("role") or "").lower() != role:
                return None
            msg = payload.get("message") or payload.get("content") or payload.get("text")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()
        return None

    message = entry.get("message")
    if isinstance(message, dict):
        msg_role = (message.get("role") or entry_type).strip().lower()
        if msg_role != role:
            return None
        return extract_content_text(message.get("content"))
    if entry_type != role:
        return None
    return extract_content_text(entry.get("content"))


def structured_event(entry: dict) -> Optional[dict[str, Any]]:
    if not isinstance(entry, dict):
        return None
    entry_type = str(entry.get("type") or "").strip().lower()
    subtype = str(entry.get("subtype") or "").strip().lower() or None
    uuid = str(entry.get("uuid") or "").strip() or None
    parent_uuid = str(entry.get("parentUuid") or "").strip() or None

    user_msg = extract_message(entry, "user")
    if user_msg:
        return {
            "role": "user",
            "text": user_msg,
            "entry_type": entry_type,
            "subtype": subtype,
            "uuid": uuid,
            "parent_uuid": parent_uuid,
            "stop_reason": None,
            "entry": entry,
        }

    assistant_msg = extract_message(entry, "assistant")
    if assistant_msg:
        stop_reason = None
        message = entry.get("message")
        if isinstance(message, dict):
            raw_stop_reason = message.get("stop_reason")
            if isinstance(raw_stop_reason, str) and raw_stop_reason.strip():
                stop_reason = raw_stop_reason.strip()
        return {
            "role": "assistant",
            "text": assistant_msg,
            "entry_type": entry_type,
            "subtype": subtype,
            "uuid": uuid,
            "parent_uuid": parent_uuid,
            "stop_reason": stop_reason,
            "entry": entry,
        }

    if entry_type == "system":
        return {
            "role": "system",
            "text": "",
            "entry_type": entry_type,
            "subtype": subtype,
            "uuid": uuid,
            "parent_uuid": parent_uuid,
            "stop_reason": None,
            "entry": entry,
        }

    return None
