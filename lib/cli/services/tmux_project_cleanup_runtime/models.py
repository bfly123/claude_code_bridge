from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectTmuxCleanupSummary:
    socket_name: str | None
    owned_panes: tuple[str, ...]
    active_panes: tuple[str, ...]
    orphaned_panes: tuple[str, ...]
    killed_panes: tuple[str, ...]


__all__ = ['ProjectTmuxCleanupSummary']
