from __future__ import annotations

from dataclasses import dataclass

from ccbd.services.project_inspection import ProjectDaemonInspection
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
    desired_state: str
    health: str
    generation: int | None
    socket_path: str | None
    preferred_socket_path: str | None
    effective_socket_path: str | None
    socket_root_kind: str | None
    socket_fallback_reason: str | None
    socket_filesystem_hint: str | None
    tmux_socket_path: str | None
    tmux_preferred_socket_path: str | None
    tmux_effective_socket_path: str | None
    tmux_socket_root_kind: str | None
    tmux_socket_fallback_reason: str | None
    tmux_socket_filesystem_hint: str | None
    last_heartbeat_at: str | None
    pid_alive: bool
    socket_connectable: bool
    heartbeat_fresh: bool
    takeover_allowed: bool
    reason: str
    startup_id: str | None = None
    startup_stage: str | None = None
    last_progress_at: str | None = None
    startup_deadline_at: str | None = None
    last_failure_reason: str | None = None
    shutdown_intent: str | None = None


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
    'ProjectDaemonInspection',
]
