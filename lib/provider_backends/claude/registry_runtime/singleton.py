from __future__ import annotations

from typing import Optional

from .facade import ClaudeSessionRegistry


_session_registry: Optional[ClaudeSessionRegistry] = None


def get_session_registry() -> ClaudeSessionRegistry:
    global _session_registry
    if _session_registry is None:
        _session_registry = ClaudeSessionRegistry()
        _session_registry.start_monitor()
    return _session_registry


__all__ = ["get_session_registry"]
