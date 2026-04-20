from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


SCHEMA_VERSION = 1


class HeartbeatAction(str, Enum):
    IDLE = 'idle'
    RESET = 'reset'
    ENTER = 'enter'
    REPEAT = 'repeat'


@dataclass(frozen=True)
class HeartbeatPolicy:
    silence_start_after_s: float
    repeat_interval_s: float
    max_notice_count: int | None = None

    def __post_init__(self) -> None:
        if float(self.silence_start_after_s) < 0:
            raise ValueError('silence_start_after_s cannot be negative')
        if float(self.repeat_interval_s) <= 0:
            raise ValueError('repeat_interval_s must be positive')
        if self.max_notice_count is not None and int(self.max_notice_count) <= 0:
            raise ValueError('max_notice_count must be positive when set')


@dataclass(frozen=True)
class HeartbeatState:
    subject_kind: str
    subject_id: str
    owner: str
    last_progress_at: str
    last_notice_at: str | None
    heartbeat_started_at: str | None
    notice_count: int
    updated_at: str

    def __post_init__(self) -> None:
        if not str(self.subject_kind or '').strip():
            raise ValueError('subject_kind cannot be empty')
        if not str(self.subject_id or '').strip():
            raise ValueError('subject_id cannot be empty')
        if not str(self.owner or '').strip():
            raise ValueError('owner cannot be empty')
        if not str(self.last_progress_at or '').strip():
            raise ValueError('last_progress_at cannot be empty')
        if int(self.notice_count) < 0:
            raise ValueError('notice_count cannot be negative')
        if not str(self.updated_at or '').strip():
            raise ValueError('updated_at cannot be empty')

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'heartbeat_state',
            'subject_kind': self.subject_kind,
            'subject_id': self.subject_id,
            'owner': self.owner,
            'last_progress_at': self.last_progress_at,
            'last_notice_at': self.last_notice_at,
            'heartbeat_started_at': self.heartbeat_started_at,
            'notice_count': self.notice_count,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'HeartbeatState':
        if record.get('schema_version') != SCHEMA_VERSION:
            raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
        if record.get('record_type') != 'heartbeat_state':
            raise ValueError("record_type must be 'heartbeat_state'")
        return cls(
            subject_kind=str(record['subject_kind']),
            subject_id=str(record['subject_id']),
            owner=str(record['owner']),
            last_progress_at=str(record['last_progress_at']),
            last_notice_at=str(record.get('last_notice_at') or '').strip() or None,
            heartbeat_started_at=str(record.get('heartbeat_started_at') or '').strip() or None,
            notice_count=int(record.get('notice_count', 0)),
            updated_at=str(record['updated_at']),
        )


@dataclass(frozen=True)
class HeartbeatDecision:
    action: HeartbeatAction
    subject_kind: str
    subject_id: str
    owner: str
    last_progress_at: str
    last_notice_at: str | None
    silence_seconds: float
    notice_count: int

    @property
    def notice_due(self) -> bool:
        return self.action in {HeartbeatAction.ENTER, HeartbeatAction.REPEAT}


__all__ = [
    'HeartbeatAction',
    'HeartbeatDecision',
    'HeartbeatPolicy',
    'HeartbeatState',
    'SCHEMA_VERSION',
]
