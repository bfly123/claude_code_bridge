from __future__ import annotations

from dataclasses import dataclass

from ..tmux_project_cleanup import ProjectTmuxCleanupSummary


class CcbdServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class DaemonHandle:
    client: object | None
    inspection: object
    started: bool = False


@dataclass(frozen=True)
class LocalPingSummary:
    project_id: str
    mount_state: str
    health: str
    generation: int | None
    socket_path: str | None
    last_heartbeat_at: str | None
    pid_alive: bool
    socket_connectable: bool
    heartbeat_fresh: bool
    takeover_allowed: bool
    reason: str


@dataclass(frozen=True)
class KillSummary:
    project_id: str
    state: str
    socket_path: str
    forced: bool
    cleanup_summaries: tuple[ProjectTmuxCleanupSummary, ...] = ()
    worktree_warnings: tuple[object, ...] = ()


__all__ = [
    'CcbdServiceError',
    'DaemonHandle',
    'KillSummary',
    'LocalPingSummary',
]
