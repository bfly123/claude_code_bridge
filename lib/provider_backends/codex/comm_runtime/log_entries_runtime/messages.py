from __future__ import annotations

from typing import Optional


def extract_message(entry: dict) -> Optional[str]:
    entry_type = entry.get("type")
    payload = _payload_dict(entry)

    if entry_type == "response_item":
        return _response_item_message(payload)
    if entry_type == "event_msg":
        return _event_message(payload)
    if payload.get("role") == "assistant":
        return _first_nonempty_text(payload.get("message"), payload.get("content"), payload.get("text"))
    return None


def extract_user_message(entry: dict) -> Optional[str]:
    entry_type = entry.get("type")
    payload = _payload_dict(entry)

    if entry_type == "event_msg" and payload.get("type") == "user_message":
        return _first_nonempty_text(payload.get("message"))
    if entry_type == "response_item" and payload.get("type") == "message" and payload.get("role") == "user":
        return _join_response_item_user_text(payload.get("content") or [])
    return None


def _response_item_message(payload: dict) -> Optional[str]:
    if payload.get("type") != "message" or payload.get("role") == "user":
        return None
    content = payload.get("content") or []
    if isinstance(content, list):
        text = _join_response_item_assistant_text(content)
        if text:
            return text
    elif isinstance(content, str) and content.strip():
        return content.strip()
    return _first_nonempty_text(payload.get("message"))


def _event_message(payload: dict) -> Optional[str]:
    payload_type = payload.get("type")
    if payload_type not in ("agent_message", "assistant_message", "assistant", "assistant_response", "message"):
        return None
    if payload.get("role") == "user":
        return None
    return _first_nonempty_text(payload.get("message"), payload.get("content"), payload.get("text"))


def _join_response_item_assistant_text(content: list[object]) -> Optional[str]:
    texts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") not in ("output_text", "text"):
            continue
        text = _first_nonempty_text(item.get("text"))
        if text:
            texts.append(text)
    if not texts:
        return None
    return "\n".join(texts).strip()


def _join_response_item_user_text(content: object) -> Optional[str]:
    if not isinstance(content, list):
        return None
    texts: list[str] = []
    for item in content:
        if not isinstance(item, dict) or item.get("type") != "input_text":
            continue
        text = _first_nonempty_text(item.get("text", ""))
        if text:
            texts.append(text)
    if not texts:
        return None
    return "\n".join(texts).strip()


def _payload_dict(entry: dict) -> dict:
    payload = entry.get("payload", {})
    return payload if isinstance(payload, dict) else {}


def _first_nonempty_text(*values: object) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


__all__ = ['extract_message', 'extract_user_message']
