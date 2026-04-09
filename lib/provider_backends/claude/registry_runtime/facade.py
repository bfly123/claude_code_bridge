from __future__ import annotations

from pathlib import Path

from .facade_monitoring import ClaudeRegistryMonitoringMixin
from .facade_sessions import ClaudeRegistrySessionMixin
from .facade_state import ClaudeRegistryStateMixin
from .facade_watchers import ClaudeRegistryWatcherMixin
from .settings import CLAUDE_PROJECTS_ROOT
from .state import RegistryRuntimeState, SessionEntry, WatcherEntry


class ClaudeSessionRegistry(
    ClaudeRegistryMonitoringMixin,
    ClaudeRegistrySessionMixin,
    ClaudeRegistryWatcherMixin,
    ClaudeRegistryStateMixin,
):
    """Manages and monitors all active Claude sessions."""

    CHECK_INTERVAL = 10.0

    def __init__(self, *, claude_root: Path = CLAUDE_PROJECTS_ROOT):
        self._runtime_state = RegistryRuntimeState()
        self._claude_root = claude_root
        self._session_entry_cls = SessionEntry
        self._watcher_entry_cls = WatcherEntry


__all__ = ['ClaudeSessionRegistry']
