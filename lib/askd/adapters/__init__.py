"""
Provider adapters for the unified ask daemon.

Each adapter wraps an existing provider's session/protocol/comm modules
to provide a consistent interface for the unified daemon.
"""
from __future__ import annotations

__all__ = [
    "BaseProviderAdapter",
    "CodexAdapter",
    "GeminiAdapter",
    "OpenCodeAdapter",
    "DroidAdapter",
    "ClaudeAdapter",
]
