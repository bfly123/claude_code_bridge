from __future__ import annotations

from typing import Any

from .scanning import latest_session


def capture_state(reader) -> dict[str, Any]:
    session = latest_session(reader)
    offset = 0
    if session and session.exists():
        try:
            offset = session.stat().st_size
        except OSError:
            offset = 0
    state: dict[str, Any] = {"session_path": session, "offset": offset, "carry": b""}
    if reader._include_subagents and session:
        from ..subagents import subagent_state_for_session

        state["subagents"] = subagent_state_for_session(reader, session, start_from_end=True)
    return state


__all__ = ["capture_state"]
