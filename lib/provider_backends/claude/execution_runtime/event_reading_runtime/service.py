from __future__ import annotations


def read_events(reader, state: dict[str, object]) -> tuple[list[dict[str, object]], dict[str, object]]:
    if hasattr(reader, "try_get_entries"):
        entries, new_state = reader.try_get_entries(state)
        return normalize_entry_dicts(entries), new_state
    events, new_state = reader.try_get_events(state)
    return normalize_tuple_events(events), new_state


def normalize_entry_dicts(entries) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for entry in entries or []:
        if isinstance(entry, dict):
            normalized.append(dict(entry))
    return normalized


def normalize_tuple_events(events) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for event in events or []:
        if not isinstance(event, tuple) or len(event) != 2:
            continue
        role, text = event
        normalized.append({"role": role, "text": text})
    return normalized


__all__ = ['normalize_entry_dicts', 'normalize_tuple_events', 'read_events']
