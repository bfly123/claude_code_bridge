from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from mailbox_targets import normalize_mailbox_owner_name

SCHEMA_VERSION = 1


class MailboxState(str, Enum):
    IDLE = 'idle'
    DELIVERING = 'delivering'
    BLOCKED = 'blocked'
    RECOVERING = 'recovering'
    DEGRADED = 'degraded'


class InboundEventType(str, Enum):
    TASK_REQUEST = 'task_request'
    TASK_REPLY = 'task_reply'
    COMPLETION_NOTICE = 'completion_notice'
    RETRY_SIGNAL = 'retry_signal'
    SYSTEM_SIGNAL = 'system_signal'
    BARRIER_RELEASE = 'barrier_release'


class InboundEventStatus(str, Enum):
    CREATED = 'created'
    QUEUED = 'queued'
    DELIVERING = 'delivering'
    CONSUMED = 'consumed'
    SUPERSEDED = 'superseded'
    ABANDONED = 'abandoned'


class LeaseState(str, Enum):
    ACQUIRED = 'acquired'
    RELEASED = 'released'
    EXPIRED = 'expired'
    ORPHANED = 'orphaned'


@dataclass(frozen=True)
class MailboxRecord:
    mailbox_id: str
    agent_name: str
    active_inbound_event_id: str | None
    queue_depth: int
    pending_reply_count: int
    last_inbound_started_at: str | None
    last_inbound_finished_at: str | None
    mailbox_state: MailboxState
    lease_version: int
    updated_at: str

    def __post_init__(self) -> None:
        if not self.mailbox_id:
            raise ValueError('mailbox_id cannot be empty')
        if not self.agent_name:
            raise ValueError('agent_name cannot be empty')
        if self.queue_depth < 0:
            raise ValueError('queue_depth cannot be negative')
        if self.pending_reply_count < 0:
            raise ValueError('pending_reply_count cannot be negative')
        if self.lease_version < 0:
            raise ValueError('lease_version cannot be negative')
        object.__setattr__(self, 'agent_name', normalize_mailbox_owner_name(self.agent_name))
        object.__setattr__(self, 'mailbox_state', MailboxState(self.mailbox_state))

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'mailbox_record',
            'mailbox_id': self.mailbox_id,
            'agent_name': self.agent_name,
            'active_inbound_event_id': self.active_inbound_event_id,
            'queue_depth': self.queue_depth,
            'pending_reply_count': self.pending_reply_count,
            'last_inbound_started_at': self.last_inbound_started_at,
            'last_inbound_finished_at': self.last_inbound_finished_at,
            'mailbox_state': self.mailbox_state.value,
            'lease_version': self.lease_version,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'MailboxRecord':
        _validate_record(record, 'mailbox_record')
        return cls(
            mailbox_id=str(record['mailbox_id']),
            agent_name=str(record['agent_name']),
            active_inbound_event_id=record.get('active_inbound_event_id'),
            queue_depth=int(record.get('queue_depth', 0)),
            pending_reply_count=int(record.get('pending_reply_count', 0)),
            last_inbound_started_at=record.get('last_inbound_started_at'),
            last_inbound_finished_at=record.get('last_inbound_finished_at'),
            mailbox_state=MailboxState(str(record.get('mailbox_state', MailboxState.IDLE.value))),
            lease_version=int(record.get('lease_version', 0)),
            updated_at=str(record.get('updated_at') or ''),
        )


@dataclass(frozen=True)
class InboundEventRecord:
    inbound_event_id: str
    agent_name: str
    event_type: InboundEventType
    message_id: str
    attempt_id: str | None
    payload_ref: str | None
    priority: int
    status: InboundEventStatus
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None

    def __post_init__(self) -> None:
        if not self.inbound_event_id:
            raise ValueError('inbound_event_id cannot be empty')
        if not self.agent_name:
            raise ValueError('agent_name cannot be empty')
        if not self.message_id:
            raise ValueError('message_id cannot be empty')
        if self.priority < 0:
            raise ValueError('priority cannot be negative')
        object.__setattr__(self, 'agent_name', normalize_mailbox_owner_name(self.agent_name))
        object.__setattr__(self, 'event_type', InboundEventType(self.event_type))
        object.__setattr__(self, 'status', InboundEventStatus(self.status))

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'inbound_event_record',
            'inbound_event_id': self.inbound_event_id,
            'agent_name': self.agent_name,
            'event_type': self.event_type.value,
            'message_id': self.message_id,
            'attempt_id': self.attempt_id,
            'payload_ref': self.payload_ref,
            'priority': self.priority,
            'status': self.status.value,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'finished_at': self.finished_at,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'InboundEventRecord':
        _validate_record(record, 'inbound_event_record')
        return cls(
            inbound_event_id=str(record['inbound_event_id']),
            agent_name=str(record['agent_name']),
            event_type=InboundEventType(str(record['event_type'])),
            message_id=str(record['message_id']),
            attempt_id=record.get('attempt_id'),
            payload_ref=record.get('payload_ref'),
            priority=int(record.get('priority', 0)),
            status=InboundEventStatus(str(record.get('status', InboundEventStatus.QUEUED.value))),
            created_at=str(record.get('created_at') or ''),
            started_at=record.get('started_at'),
            finished_at=record.get('finished_at'),
        )


@dataclass(frozen=True)
class DeliveryLease:
    agent_name: str
    inbound_event_id: str
    lease_version: int
    acquired_at: str
    last_progress_at: str | None
    expires_at: str | None
    lease_state: LeaseState

    def __post_init__(self) -> None:
        if not self.agent_name:
            raise ValueError('agent_name cannot be empty')
        if not self.inbound_event_id:
            raise ValueError('inbound_event_id cannot be empty')
        if self.lease_version < 0:
            raise ValueError('lease_version cannot be negative')
        object.__setattr__(self, 'agent_name', normalize_mailbox_owner_name(self.agent_name))
        object.__setattr__(self, 'lease_state', LeaseState(self.lease_state))

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'delivery_lease',
            'agent_name': self.agent_name,
            'inbound_event_id': self.inbound_event_id,
            'lease_version': self.lease_version,
            'acquired_at': self.acquired_at,
            'last_progress_at': self.last_progress_at,
            'expires_at': self.expires_at,
            'lease_state': self.lease_state.value,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'DeliveryLease':
        _validate_record(record, 'delivery_lease')
        return cls(
            agent_name=str(record['agent_name']),
            inbound_event_id=str(record['inbound_event_id']),
            lease_version=int(record.get('lease_version', 0)),
            acquired_at=str(record.get('acquired_at') or ''),
            last_progress_at=record.get('last_progress_at'),
            expires_at=record.get('expires_at'),
            lease_state=LeaseState(str(record.get('lease_state', LeaseState.ACQUIRED.value))),
        )


def _validate_record(record: dict[str, Any], expected_type: str) -> None:
    if record.get('schema_version') != SCHEMA_VERSION:
        raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
    if record.get('record_type') != expected_type:
        raise ValueError(f'record_type must be {expected_type!r}')


__all__ = [
    'DeliveryLease',
    'InboundEventRecord',
    'InboundEventStatus',
    'InboundEventType',
    'LeaseState',
    'MailboxRecord',
    'MailboxState',
    'SCHEMA_VERSION',
]
