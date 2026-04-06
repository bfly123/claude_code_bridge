from __future__ import annotations

from typing import Any


def extract_message(entry: dict, role: str) -> str | None:
    if not isinstance(entry, dict):
        return None
    entry_type = str(entry.get("type") or "").strip().lower()
    if entry_type == "message":
        message = entry.get("message")
        if isinstance(message, dict):
            msg_role = str(message.get("role") or "").strip().lower()
            if msg_role == role:
                return _extract_content_text(message.get("content"))
    msg_role = str(entry.get("role") or entry_type).strip().lower()
    if msg_role == role:
        return _extract_content_text(entry.get("content") or entry.get("message"))
    return None


def _extract_content_text(content: Any) -> str | None:
    if content is None:
        return None
    if isinstance(content, str):
        return content.strip() or None
    if not isinstance(content, list):
        return None
    texts: list[str] = []
    for item in content:
        text = _extract_text_fragment(item)
        if text:
            texts.append(text)
    if not texts:
        return None
    return "\n".join(texts).strip()


def _extract_text_fragment(item: object) -> str | None:
    if not isinstance(item, dict):
        return None
    item_type = str(item.get("type") or "").strip().lower()
    if item_type in {"thinking", "thinking_delta"}:
        return None
    text = item.get("text")
    if not text and item_type == "text":
        text = item.get("content")
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    return stripped or None


__all__ = ["extract_message"]
