from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from .common import API_VERSION, SCHEMA_VERSION, CcbdModelError


class MountState(str, Enum):
    MOUNTED = 'mounted'
    UNMOUNTED = 'unmounted'


class LeaseHealth(str, Enum):
    HEALTHY = 'healthy'
    DEGRADED = 'degraded'
    STALE = 'stale'
    UNMOUNTED = 'unmounted'
    MISSING = 'missing'


@dataclass(frozen=True)
class CcbdLease:
    project_id: str
    ccbd_pid: int
    socket_path: str
    owner_uid: int
    boot_id: str
    started_at: str
    last_heartbeat_at: str
    mount_state: MountState
    generation: int = 1
    config_signature: str | None = None
    keeper_pid: int | None = None
    daemon_instance_id: str | None = None
    api_version: int = API_VERSION

    def __post_init__(self) -> None:
        if self.api_version != API_VERSION:
            raise CcbdModelError(f'api_version must be {API_VERSION}')
        if not (self.project_id or '').strip():
            raise CcbdModelError('project_id cannot be empty')
        if self.ccbd_pid <= 0:
            raise CcbdModelError('ccbd_pid must be positive')
        if not (self.socket_path or '').strip():
            raise CcbdModelError('socket_path cannot be empty')
        if not (self.boot_id or '').strip():
            raise CcbdModelError('boot_id cannot be empty')
        if not (self.started_at or '').strip():
            raise CcbdModelError('started_at cannot be empty')
        if not (self.last_heartbeat_at or '').strip():
            raise CcbdModelError('last_heartbeat_at cannot be empty')
        if self.generation <= 0:
            raise CcbdModelError('generation must be positive')
        if self.config_signature is not None and not str(self.config_signature).strip():
            raise CcbdModelError('config_signature cannot be blank')
        if self.keeper_pid is not None and int(self.keeper_pid) <= 0:
            raise CcbdModelError('keeper_pid must be positive when provided')
        if self.daemon_instance_id is not None and not str(self.daemon_instance_id).strip():
            raise CcbdModelError('daemon_instance_id cannot be blank')

    def with_heartbeat(self, timestamp: str) -> CcbdLease:
        return replace(self, last_heartbeat_at=timestamp)

    def with_mount_state(self, mount_state: MountState, *, heartbeat_at: str) -> CcbdLease:
        return replace(self, mount_state=mount_state, last_heartbeat_at=heartbeat_at)

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'ccbd_lease',
            'api_version': self.api_version,
            'project_id': self.project_id,
            'ccbd_pid': self.ccbd_pid,
            'socket_path': self.socket_path,
            'owner_uid': self.owner_uid,
            'boot_id': self.boot_id,
            'started_at': self.started_at,
            'last_heartbeat_at': self.last_heartbeat_at,
            'mount_state': self.mount_state.value,
            'generation': self.generation,
            'config_signature': self.config_signature,
            'keeper_pid': self.keeper_pid,
            'daemon_instance_id': self.daemon_instance_id,
        }


@dataclass(frozen=True)
class LeaseInspection:
    lease: CcbdLease | None
    health: LeaseHealth
    pid_alive: bool
    socket_connectable: bool
    heartbeat_fresh: bool
    takeover_allowed: bool
    reason: str

    @property
    def generation(self) -> int | None:
        if self.lease is None:
            return None
        return self.lease.generation

    def to_record(self) -> dict[str, Any]:
        return {
            'health': self.health.value,
            'pid_alive': self.pid_alive,
            'socket_connectable': self.socket_connectable,
            'heartbeat_fresh': self.heartbeat_fresh,
            'takeover_allowed': self.takeover_allowed,
            'reason': self.reason,
            'lease': self.lease.to_record() if self.lease else None,
        }


__all__ = ['CcbdLease', 'LeaseHealth', 'LeaseInspection', 'MountState']
