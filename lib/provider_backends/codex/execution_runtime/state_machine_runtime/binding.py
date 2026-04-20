from __future__ import annotations

from .models import CodexPollState


def update_binding_refs(poll: CodexPollState, entry: dict[str, object]) -> None:
    entry_turn_id = str(entry.get("turn_id") or "").strip()
    if entry_turn_id:
        poll.bound_turn_id = entry_turn_id
    entry_task_id = str(entry.get("task_id") or "").strip()
    if entry_task_id:
        poll.bound_task_id = entry_task_id


__all__ = ["update_binding_refs"]
