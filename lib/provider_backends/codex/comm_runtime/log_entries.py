from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def extract_message(entry: dict) -> Optional[str]:
    entry_type = entry.get("type")
    payload = entry.get("payload", {})

    if entry_type == "response_item":
        if payload.get("type") != "message":
            return None
        if payload.get("role") == "user":
            return None

        content = payload.get("content") or []
        if isinstance(content, list):
            texts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") in ("output_text", "text"):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        texts.append(text.strip())
            if texts:
                return "\n".join(texts).strip()
        elif isinstance(content, str) and content.strip():
            return content.strip()

        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
        return None

    if entry_type == "event_msg":
        payload_type = payload.get("type")
        if payload_type in ("agent_message", "assistant_message", "assistant", "assistant_response", "message"):
            if payload.get("role") == "user":
                return None
            msg = payload.get("message") or payload.get("content") or payload.get("text")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()
        return None

    if payload.get("role") == "assistant":
        msg = payload.get("message") or payload.get("content") or payload.get("text")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()
    return None


def extract_user_message(entry: dict) -> Optional[str]:
    entry_type = entry.get("type")
    payload = entry.get("payload", {})

    if entry_type == "event_msg" and payload.get("type") == "user_message":
        msg = payload.get("message", "")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()

    if entry_type == "response_item":
        if payload.get("type") == "message" and payload.get("role") == "user":
            content = payload.get("content") or []
            texts = [item.get("text", "") for item in content if item.get("type") == "input_text"]
            if texts:
                return "\n".join(filter(None, texts)).strip()
    return None


def extract_entry(entry: dict) -> Optional[Dict[str, Any]]:
    entry_type = str(entry.get("type") or "").strip()
    payload = entry.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}
    payload_type = str(payload.get("type") or "").strip()
    timestamp = entry.get("timestamp")

    base: Dict[str, Any] = {
        "entry_type": entry_type,
        "payload_type": payload_type,
        "timestamp": timestamp,
        "phase": payload.get("phase"),
        "turn_id": payload.get("turn_id"),
        "task_id": payload.get("task_id"),
        "reason": payload.get("reason"),
        "last_agent_message": payload.get("last_agent_message"),
        "entry": entry,
    }

    if entry_type == "response_item" and payload_type == "message":
        role = str(payload.get("role") or "").strip().lower()
        if role == "user":
            text = extract_user_message(entry) or ""
            return {**base, "role": "user", "text": text}
        if role == "assistant":
            text = extract_message(entry) or ""
            return {**base, "role": "assistant", "text": text}
        return None

    if entry_type == "event_msg":
        if payload_type == "user_message":
            text = extract_user_message(entry) or ""
            return {**base, "role": "user", "text": text}
        if payload_type in {"agent_message", "assistant_message", "assistant", "assistant_response", "message"}:
            role = str(payload.get("role") or "").strip().lower()
            if role == "user":
                text = extract_user_message(entry) or ""
                return {**base, "role": "user", "text": text}
            text = extract_message(entry) or ""
            return {**base, "role": "assistant", "text": text}
        if payload_type == "task_complete":
            text = str(payload.get("last_agent_message") or "").strip()
            return {**base, "role": "system", "text": text, "reason": "task_complete"}
        if payload_type == "turn_aborted":
            return {
                **base,
                "role": "system",
                "text": str(payload.get("message") or "").strip(),
                "reason": payload.get("reason") or "turn_aborted",
            }

    user_msg = extract_user_message(entry)
    if isinstance(user_msg, str) and user_msg.strip():
        return {**base, "role": "user", "text": user_msg.strip()}
    ai_msg = extract_message(entry)
    if isinstance(ai_msg, str) and ai_msg.strip():
        role = str(payload.get("role") or "assistant").strip().lower()
        return {**base, "role": role if role else "assistant", "text": ai_msg.strip()}
    return None


def extract_event(entry: dict) -> Optional[Tuple[str, str]]:
    normalized = extract_entry(entry)
    if normalized is None:
        return None
    role = str(normalized.get("role") or "").strip().lower()
    text = str(normalized.get("text") or "").strip()
    if role in {"user", "assistant"} and text:
        return role, text
    return None
