from __future__ import annotations

from pathlib import Path
from typing import Any


def remember_log_hint(comm, state: dict[str, Any] | None) -> Path | None:
    log_hint = _state_log_hint(comm, state)
    comm._remember_codex_session(log_hint)
    return log_hint


def ensure_session_health(comm) -> None:
    healthy, status = comm._check_session_health_impl(probe_terminal=False)
    if not healthy:
        raise RuntimeError(f"❌ Session error: {status}")


def _state_log_hint(comm, state: dict[str, Any] | None) -> Path | None:
    if isinstance(state, dict):
        log_hint = state.get("log_path")
        if isinstance(log_hint, Path):
            return log_hint
        if isinstance(log_hint, str) and log_hint.strip():
            return Path(log_hint)
    current = comm.log_reader.current_log_path()
    if isinstance(current, Path):
        return current
    if isinstance(current, str) and current.strip():
        return Path(current)
    return None


__all__ = ["ensure_session_health", "remember_log_hint"]
