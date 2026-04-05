from __future__ import annotations


def read_events(reader, state: dict[str, object]) -> tuple[list[dict[str, object]], dict[str, object]]:
    if hasattr(reader, "try_get_entries"):
        entries, new_state = reader.try_get_entries(state)
        normalized: list[dict[str, object]] = []
        for entry in entries or []:
            if isinstance(entry, dict):
                normalized.append(dict(entry))
        return normalized, new_state

    events, new_state = reader.try_get_events(state)
    normalized = []
    for event in events or []:
        if not isinstance(event, tuple) or len(event) != 2:
            continue
        role, text = event
        normalized.append({"role": role, "text": text})
    return normalized, new_state


def is_turn_boundary_event(event: dict[str, object], *, last_assistant_uuid: str) -> bool:
    entry_type = str(event.get("entry_type") or "").strip().lower()
    subtype = str(event.get("subtype") or "").strip().lower()
    parent_uuid = str(event.get("parent_uuid") or "").strip()
    if entry_type != "system" or subtype != "turn_duration":
        return False
    if not last_assistant_uuid:
        return False
    return parent_uuid == last_assistant_uuid


def terminal_api_error_payload(event: dict[str, object]) -> dict[str, object] | None:
    entry_type = str(event.get("entry_type") or "").strip().lower()
    subtype = str(event.get("subtype") or "").strip().lower()
    if entry_type != "system" or subtype != "api_error":
        return None
    raw_entry = event.get("entry")
    if not isinstance(raw_entry, dict):
        return None
    try:
        retry_attempt = int(raw_entry.get("retryAttempt"))
        max_retries = int(raw_entry.get("maxRetries"))
    except Exception:
        return None
    if max_retries <= 0 or retry_attempt < max_retries:
        return None
    cause = raw_entry.get("cause")
    if not isinstance(cause, dict):
        cause = {}
    error_code = str(cause.get("code") or "").strip() or None
    error_path = str(cause.get("path") or "").strip() or None
    message_parts = ["Claude API request failed"]
    if error_code:
        message_parts.append(f"code={error_code}")
    if error_path:
        message_parts.append(f"path={error_path}")
    return {
        "message": " ".join(message_parts),
        "error_code": error_code,
        "error_path": error_path,
        "retry_attempt": retry_attempt,
        "max_retries": max_retries,
        "timestamp": str(raw_entry.get("timestamp") or ""),
    }


__all__ = ["is_turn_boundary_event", "read_events", "terminal_api_error_payload"]
