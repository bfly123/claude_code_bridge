from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from ccbd.models import SCHEMA_VERSION


_KEEPER_RECORD_TYPE = 'ccbd_keeper'
_SHUTDOWN_INTENT_RECORD_TYPE = 'ccbd_shutdown_intent'


@dataclass(frozen=True)
class KeeperState:
    project_id: str
    keeper_pid: int
    started_at: str
    last_check_at: str
    state: str
    restart_count: int = 0
    last_restart_at: str | None = None
    last_failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.keeper_pid <= 0:
            raise ValueError('keeper_pid must be positive')
        if not str(self.project_id or '').strip():
            raise ValueError('project_id cannot be empty')
        if not str(self.started_at or '').strip():
            raise ValueError('started_at cannot be empty')
        if not str(self.last_check_at or '').strip():
            raise ValueError('last_check_at cannot be empty')
        if not str(self.state or '').strip():
            raise ValueError('state cannot be empty')
        if self.restart_count < 0:
            raise ValueError('restart_count cannot be negative')

    def with_check(self, occurred_at: str) -> KeeperState:
        return replace(self, last_check_at=occurred_at)

    def with_state(self, state: str, *, occurred_at: str) -> KeeperState:
        return replace(self, state=state, last_check_at=occurred_at)

    def with_restart_attempt(self, *, occurred_at: str) -> KeeperState:
        return replace(
            self,
            last_check_at=occurred_at,
            restart_count=self.restart_count + 1,
            last_restart_at=occurred_at,
        )

    def with_failure(self, *, occurred_at: str, reason: str) -> KeeperState:
        return replace(
            self,
            last_check_at=occurred_at,
            last_failure_reason=str(reason or '').strip() or 'unknown_failure',
        )

    def with_success(self, *, occurred_at: str) -> KeeperState:
        return replace(
            self,
            last_check_at=occurred_at,
            restart_count=0,
            last_restart_at=None,
            last_failure_reason=None,
        )

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': _KEEPER_RECORD_TYPE,
            'project_id': self.project_id,
            'keeper_pid': self.keeper_pid,
            'started_at': self.started_at,
            'last_check_at': self.last_check_at,
            'state': self.state,
            'restart_count': self.restart_count,
            'last_restart_at': self.last_restart_at,
            'last_failure_reason': self.last_failure_reason,
        }

    @classmethod
    def from_record(cls, payload: dict[str, Any]) -> KeeperState:
        if payload.get('schema_version') != SCHEMA_VERSION:
            raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
        if payload.get('record_type') != _KEEPER_RECORD_TYPE:
            raise ValueError(f"record_type must be '{_KEEPER_RECORD_TYPE}'")
        return cls(
            project_id=str(payload['project_id']),
            keeper_pid=int(payload['keeper_pid']),
            started_at=str(payload['started_at']),
            last_check_at=str(payload['last_check_at']),
            state=str(payload['state']),
            restart_count=int(payload.get('restart_count', 0)),
            last_restart_at=str(payload.get('last_restart_at') or '').strip() or None,
            last_failure_reason=str(payload.get('last_failure_reason') or '').strip() or None,
        )


@dataclass(frozen=True)
class ShutdownIntent:
    project_id: str
    requested_at: str
    requested_by_pid: int
    reason: str

    def __post_init__(self) -> None:
        if not str(self.project_id or '').strip():
            raise ValueError('project_id cannot be empty')
        if not str(self.requested_at or '').strip():
            raise ValueError('requested_at cannot be empty')
        if self.requested_by_pid <= 0:
            raise ValueError('requested_by_pid must be positive')
        if not str(self.reason or '').strip():
            raise ValueError('reason cannot be empty')

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': _SHUTDOWN_INTENT_RECORD_TYPE,
            'project_id': self.project_id,
            'requested_at': self.requested_at,
            'requested_by_pid': self.requested_by_pid,
            'reason': self.reason,
        }

    @classmethod
    def from_record(cls, payload: dict[str, Any]) -> ShutdownIntent:
        if payload.get('schema_version') != SCHEMA_VERSION:
            raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
        if payload.get('record_type') != _SHUTDOWN_INTENT_RECORD_TYPE:
            raise ValueError(f"record_type must be '{_SHUTDOWN_INTENT_RECORD_TYPE}'")
        return cls(
            project_id=str(payload['project_id']),
            requested_at=str(payload['requested_at']),
            requested_by_pid=int(payload['requested_by_pid']),
            reason=str(payload['reason']),
        )


__all__ = ['KeeperState', 'ShutdownIntent']
