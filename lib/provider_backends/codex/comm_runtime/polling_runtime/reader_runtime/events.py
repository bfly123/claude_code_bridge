from __future__ import annotations

from typing import Any


def message_event(entry: dict[str, Any]) -> tuple[str, str] | None:
    role = str(entry.get('role') or '').strip().lower()
    text = str(entry.get('text') or '')
    if role in {'user', 'assistant'} and text.strip():
        return role, text.strip()
    return None


__all__ = ['message_event']
