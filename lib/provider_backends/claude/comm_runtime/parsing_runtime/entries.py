from __future__ import annotations

from typing import Any

from .content import extract_content_text


def extract_message(entry: dict[str, Any], role: str) -> str | None:
    if not isinstance(entry, dict):
        return None
    entry_type = str(entry.get("type") or "").strip().lower()

    if entry_type == "response_item":
        return _extract_response_item_message(entry, role)
    if entry_type == "event_msg":
        return _extract_event_message(entry, role)
    return _extract_standard_message(entry, role, entry_type=entry_type)


def _extract_response_item_message(entry: dict[str, Any], role: str) -> str | None:
    payload = entry.get("payload", {})
    if not isinstance(payload, dict) or payload.get("type") != "message":
        return None
    if str(payload.get("role") or "").lower() != role:
        return None
    return extract_content_text(payload.get("content"))


def _extract_event_message(entry: dict[str, Any], role: str) -> str | None:
    payload = entry.get("payload", {})
    if not isinstance(payload, dict):
        return None
    payload_type = str(payload.get("type") or "").lower()
    if payload_type not in {"agent_message", "assistant_message", "assistant"}:
        return None
    if str(payload.get("role") or "").lower() != role:
        return None
    for key in ("message", "content", "text"):
        message = payload.get(key)
        if isinstance(message, str) and message.strip():
            return message.strip()
    return None


def _extract_standard_message(entry: dict[str, Any], role: str, *, entry_type: str) -> str | None:
    message = entry.get("message")
    if isinstance(message, dict):
        msg_role = str(message.get("role") or entry_type).strip().lower()
        if msg_role != role:
            return None
        return extract_content_text(message.get("content"))
    if entry_type != role:
        return None
    return extract_content_text(entry.get("content"))


__all__ = ["extract_message"]
