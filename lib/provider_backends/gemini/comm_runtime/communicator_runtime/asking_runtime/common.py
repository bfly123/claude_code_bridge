from __future__ import annotations

from pathlib import Path
from typing import Any


def ensure_session_health(comm) -> None:
    healthy, status = comm._check_session_health_impl(probe_terminal=False)
    if not healthy:
        raise RuntimeError(f"❌ Session error: {status}")


def remember_session_path(comm, state: dict[str, Any] | None) -> Path | None:
    session_path = _session_path_from_state(state)
    if session_path is not None:
        comm._remember_gemini_session(session_path)
    return session_path


def _session_path_from_state(state: dict[str, Any] | None) -> Path | None:
    if not isinstance(state, dict):
        return None
    session_path = state.get("session_path")
    if isinstance(session_path, Path):
        return session_path
    if isinstance(session_path, str) and session_path.strip():
        return Path(session_path)
    return None


__all__ = ["ensure_session_health", "remember_session_path"]
