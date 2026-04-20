from __future__ import annotations


def read_entries(reader, state: dict[str, object]) -> tuple[list[dict[str, object]], dict[str, object]]:
    if hasattr(reader, "try_get_entries"):
        entries, new_state = reader.try_get_entries(state)
        normalized: list[dict[str, object]] = []
        for entry in entries or []:
            if isinstance(entry, dict):
                normalized.append(dict(entry))
        return normalized, new_state

    event, new_state = reader.try_get_event(state)
    if not isinstance(event, tuple) or len(event) != 2:
        return [], new_state
    role, text = event
    return [{"role": role, "text": text, "entry_type": role}], new_state


def assistant_signature(entry: dict[str, object]) -> str:
    text = str(entry.get("text") or "").strip()
    if not text:
        return ""
    timestamp = str(entry.get("timestamp") or "").strip()
    phase = str(entry.get("phase") or "").strip().lower()
    if not timestamp:
        return ""
    return f"{timestamp}\0{phase}\0{text}"


__all__ = ["assistant_signature", "read_entries"]
