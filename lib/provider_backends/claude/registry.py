"""
Session registry for Claude backend bindings.

Monitors active sessions and refreshes log bindings periodically to adapt to session switches.
"""

from __future__ import annotations

from .registry_runtime.facade import ClaudeSessionRegistry
from .registry_runtime.logging import write_registry_log as _write_log
from .registry_runtime.settings import CLAUDE_PROJECTS_ROOT
from .registry_runtime.singleton import get_session_registry

__all__ = [
    "CLAUDE_PROJECTS_ROOT",
    "ClaudeSessionRegistry",
    "get_session_registry",
]
