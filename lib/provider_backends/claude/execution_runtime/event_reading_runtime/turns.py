from __future__ import annotations


def is_turn_boundary_event(event: dict[str, object], *, last_assistant_uuid: str) -> bool:
    entry_type = normalized_text(event.get("entry_type"))
    subtype = normalized_text(event.get("subtype"))
    parent_uuid = str(event.get("parent_uuid") or "").strip()
    if entry_type != "system" or subtype != "turn_duration":
        return False
    if not last_assistant_uuid:
        return False
    return parent_uuid == last_assistant_uuid


def normalized_text(value: object) -> str:
    return str(value or "").strip().lower()


__all__ = ['is_turn_boundary_event', 'normalized_text']
