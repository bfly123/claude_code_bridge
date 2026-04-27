from __future__ import annotations

from dataclasses import dataclass

from ccbd.models import LeaseHealth
from ccbd.services.lifecycle import lifecycle_from_inspection


@dataclass(frozen=True)
class ProjectDaemonInspection:
    lease: object | None
    health: object
    pid_alive: bool
    socket_connectable: bool
    heartbeat_fresh: bool
    takeover_allowed: bool
    reason: str
    phase: str
    desired_state: str
    last_failure_reason: str | None = None
    shutdown_intent: str | None = None
    startup_id: str | None = None
    startup_stage: str | None = None
    last_progress_at: str | None = None
    startup_deadline_at: str | None = None
    lifecycle: object | None = None

    @property
    def generation(self) -> int | None:
        lifecycle_generation = getattr(self.lifecycle, 'generation', None)
        if lifecycle_generation is not None:
            return int(lifecycle_generation)
        if self.lease is None:
            return None
        return int(getattr(self.lease, 'generation', 0) or 0) or None

    @property
    def socket_path(self) -> str | None:
        value = str(getattr(self.lifecycle, 'socket_path', '') or '').strip()
        if value:
            return value
        if self.lease is None:
            return None
        lease_value = str(getattr(self.lease, 'socket_path', '') or '').strip()
        return lease_value or None


def load_project_daemon_inspection(
    project_id: str,
    *,
    lease_inspection,
    lifecycle_store,
    occurred_at: str,
) -> ProjectDaemonInspection:
    lifecycle = lifecycle_store.load() if lifecycle_store is not None else None
    if lifecycle is None:
        lifecycle = lifecycle_from_inspection(
            project_id=project_id,
            inspection=lease_inspection,
            occurred_at=occurred_at,
        )
    return build_project_daemon_inspection(lease_inspection, lifecycle=lifecycle)


def build_project_daemon_inspection(lease_inspection, *, lifecycle) -> ProjectDaemonInspection:
    phase = str(getattr(lifecycle, 'phase', '') or '').strip() or fallback_phase(lease_inspection)
    desired_state = str(getattr(lifecycle, 'desired_state', '') or '').strip() or fallback_desired_state(phase)
    return ProjectDaemonInspection(
        lease=lease_inspection.lease,
        health=lease_inspection.health,
        pid_alive=lease_inspection.pid_alive,
        socket_connectable=lease_inspection.socket_connectable,
        heartbeat_fresh=lease_inspection.heartbeat_fresh,
        takeover_allowed=lease_inspection.takeover_allowed,
        reason=lease_inspection.reason,
        phase=phase,
        desired_state=desired_state,
        last_failure_reason=str(getattr(lifecycle, 'last_failure_reason', '') or '').strip() or None,
        shutdown_intent=str(getattr(lifecycle, 'shutdown_intent', '') or '').strip() or None,
        startup_id=str(getattr(lifecycle, 'startup_id', '') or '').strip() or None,
        startup_stage=str(getattr(lifecycle, 'startup_stage', '') or '').strip() or None,
        last_progress_at=str(getattr(lifecycle, 'last_progress_at', '') or '').strip() or None,
        startup_deadline_at=str(getattr(lifecycle, 'startup_deadline_at', '') or '').strip() or None,
        lifecycle=lifecycle,
    )


def fallback_phase(lease_inspection) -> str:
    health = getattr(lease_inspection, 'health', None)
    if health in {LeaseHealth.MISSING, LeaseHealth.UNMOUNTED}:
        return 'unmounted'
    if health is LeaseHealth.HEALTHY:
        return 'mounted'
    return 'failed'


def fallback_desired_state(phase: str) -> str:
    return 'stopped' if phase == 'unmounted' else 'running'


__all__ = [
    'ProjectDaemonInspection',
    'build_project_daemon_inspection',
    'fallback_desired_state',
    'fallback_phase',
    'load_project_daemon_inspection',
]
