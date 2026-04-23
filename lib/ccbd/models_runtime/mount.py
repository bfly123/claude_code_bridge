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


def _require_non_empty_text(value: object, *, field_name: str) -> None:
    if not str(value or '').strip():
        raise CcbdModelError(f'{field_name} cannot be empty')


def _require_positive_int(value: int, *, field_name: str) -> None:
    if int(value) <= 0:
        raise CcbdModelError(f'{field_name} must be positive')


def _require_optional_non_empty_text(value: object | None, *, field_name: str) -> None:
    if value is not None:
        _require_non_empty_text(value, field_name=field_name)


def _require_optional_positive_int(value: int | None, *, field_name: str) -> None:
    if value is not None:
        _require_positive_int(value, field_name=field_name)


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
    ipc_kind: str | None = None
    backend_family: str | None = None
    backend_impl: str | None = None
    api_version: int = API_VERSION

    def __post_init__(self) -> None:
        if self.api_version != API_VERSION:
            raise CcbdModelError(f'api_version must be {API_VERSION}')
        _require_non_empty_text(self.project_id, field_name='project_id')
        _require_positive_int(self.ccbd_pid, field_name='ccbd_pid')
        _require_non_empty_text(self.socket_path, field_name='socket_path')
        _require_non_empty_text(self.boot_id, field_name='boot_id')
        _require_non_empty_text(self.started_at, field_name='started_at')
        _require_non_empty_text(self.last_heartbeat_at, field_name='last_heartbeat_at')
        _require_positive_int(self.generation, field_name='generation')
        _require_optional_non_empty_text(self.ipc_kind, field_name='ipc_kind')
        _require_optional_non_empty_text(self.config_signature, field_name='config_signature')
        _require_optional_positive_int(self.keeper_pid, field_name='keeper_pid')
        _require_optional_non_empty_text(self.daemon_instance_id, field_name='daemon_instance_id')
        _require_optional_non_empty_text(self.backend_family, field_name='backend_family')
        _require_optional_non_empty_text(self.backend_impl, field_name='backend_impl')

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
            'ipc_kind': self.ipc_kind,
            'owner_uid': self.owner_uid,
            'boot_id': self.boot_id,
            'started_at': self.started_at,
            'last_heartbeat_at': self.last_heartbeat_at,
            'mount_state': self.mount_state.value,
            'generation': self.generation,
            'config_signature': self.config_signature,
            'keeper_pid': self.keeper_pid,
            'daemon_instance_id': self.daemon_instance_id,
            'backend_family': self.backend_family,
            'backend_impl': self.backend_impl,
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
