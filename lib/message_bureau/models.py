from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agents.models import normalize_agent_name
from mailbox_targets import normalize_actor_name

SCHEMA_VERSION = 1


class MessageState(str, Enum):
    CREATED = 'created'
    QUEUED = 'queued'
    DISPATCHING = 'dispatching'
    RUNNING = 'running'
    PARTIALLY_REPLIED = 'partially_replied'
    COMPLETED = 'completed'
    INCOMPLETE = 'incomplete'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    DEAD_LETTER = 'dead_letter'


class AttemptState(str, Enum):
    PENDING = 'pending'
    DELIVERING = 'delivering'
    RUNNING = 'running'
    WAITING_COMPLETION = 'waiting_completion'
    REPLY_READY = 'reply_ready'
    STALLED = 'stalled'
    RUNTIME_DEAD = 'runtime_dead'
    FAILED = 'failed'
    INCOMPLETE = 'incomplete'
    CANCELLED = 'cancelled'
    SUPERSEDED = 'superseded'
    DEAD_LETTER = 'dead_letter'
    COMPLETED = 'completed'


class ReplyTerminalStatus(str, Enum):
    COMPLETED = 'completed'
    INCOMPLETE = 'incomplete'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


def _normalize_actor(actor: str) -> str:
    return normalize_actor_name(actor)


@dataclass(frozen=True)
class MessageRecord:
    message_id: str
    origin_message_id: str | None
    from_actor: str
    target_scope: str
    target_agents: tuple[str, ...] = field(default_factory=tuple)
    message_class: str = 'task_request'
    reply_policy: dict[str, Any] = field(default_factory=dict)
    retry_policy: dict[str, Any] = field(default_factory=dict)
    priority: int = 100
    payload_ref: str | None = None
    submission_id: str | None = None
    created_at: str = ''
    updated_at: str = ''
    message_state: MessageState = MessageState.CREATED

    def __post_init__(self) -> None:
        if not self.message_id:
            raise ValueError('message_id cannot be empty')
        if not self.from_actor:
            raise ValueError('from_actor cannot be empty')
        if not self.target_scope:
            raise ValueError('target_scope cannot be empty')
        if not self.target_agents:
            raise ValueError('target_agents cannot be empty')
        if not self.message_class:
            raise ValueError('message_class cannot be empty')
        if self.priority < 0:
            raise ValueError('priority cannot be negative')
        object.__setattr__(self, 'from_actor', _normalize_actor(self.from_actor))
        object.__setattr__(
            self,
            'target_agents',
            tuple(normalize_agent_name(agent_name) for agent_name in self.target_agents),
        )
        object.__setattr__(self, 'reply_policy', dict(self.reply_policy or {}))
        object.__setattr__(self, 'retry_policy', dict(self.retry_policy or {}))
        object.__setattr__(self, 'message_state', MessageState(self.message_state))

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'message_record',
            'message_id': self.message_id,
            'origin_message_id': self.origin_message_id,
            'from_actor': self.from_actor,
            'target_scope': self.target_scope,
            'target_agents': list(self.target_agents),
            'message_class': self.message_class,
            'reply_policy': dict(self.reply_policy),
            'retry_policy': dict(self.retry_policy),
            'priority': self.priority,
            'payload_ref': self.payload_ref,
            'submission_id': self.submission_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'message_state': self.message_state.value,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'MessageRecord':
        _validate_record(record, 'message_record')
        return cls(
            message_id=str(record['message_id']),
            origin_message_id=record.get('origin_message_id'),
            from_actor=str(record['from_actor']),
            target_scope=str(record['target_scope']),
            target_agents=tuple(record.get('target_agents') or ()),
            message_class=str(record.get('message_class') or 'task_request'),
            reply_policy=dict(record.get('reply_policy') or {}),
            retry_policy=dict(record.get('retry_policy') or {}),
            priority=int(record.get('priority', 100)),
            payload_ref=record.get('payload_ref'),
            submission_id=record.get('submission_id'),
            created_at=str(record.get('created_at') or ''),
            updated_at=str(record.get('updated_at') or ''),
            message_state=MessageState(str(record.get('message_state', MessageState.CREATED.value))),
        )


@dataclass(frozen=True)
class AttemptRecord:
    attempt_id: str
    message_id: str
    agent_name: str
    provider: str
    job_id: str
    retry_index: int
    health_snapshot_ref: str | None
    started_at: str
    updated_at: str
    attempt_state: AttemptState

    def __post_init__(self) -> None:
        if not self.attempt_id:
            raise ValueError('attempt_id cannot be empty')
        if not self.message_id:
            raise ValueError('message_id cannot be empty')
        if not self.agent_name:
            raise ValueError('agent_name cannot be empty')
        if not self.provider:
            raise ValueError('provider cannot be empty')
        if not self.job_id:
            raise ValueError('job_id cannot be empty')
        if self.retry_index < 0:
            raise ValueError('retry_index cannot be negative')
        object.__setattr__(self, 'agent_name', normalize_agent_name(self.agent_name))
        object.__setattr__(self, 'attempt_state', AttemptState(self.attempt_state))

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'attempt_record',
            'attempt_id': self.attempt_id,
            'message_id': self.message_id,
            'agent_name': self.agent_name,
            'provider': self.provider,
            'job_id': self.job_id,
            'retry_index': self.retry_index,
            'health_snapshot_ref': self.health_snapshot_ref,
            'started_at': self.started_at,
            'updated_at': self.updated_at,
            'attempt_state': self.attempt_state.value,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'AttemptRecord':
        _validate_record(record, 'attempt_record')
        return cls(
            attempt_id=str(record['attempt_id']),
            message_id=str(record['message_id']),
            agent_name=str(record['agent_name']),
            provider=str(record['provider']),
            job_id=str(record['job_id']),
            retry_index=int(record.get('retry_index', 0)),
            health_snapshot_ref=record.get('health_snapshot_ref'),
            started_at=str(record.get('started_at') or ''),
            updated_at=str(record.get('updated_at') or ''),
            attempt_state=AttemptState(str(record.get('attempt_state', AttemptState.PENDING.value))),
        )


@dataclass(frozen=True)
class ReplyRecord:
    reply_id: str
    message_id: str
    attempt_id: str
    agent_name: str
    terminal_status: ReplyTerminalStatus
    reply: str
    diagnostics: dict[str, Any] = field(default_factory=dict)
    finished_at: str = ''

    def __post_init__(self) -> None:
        if not self.reply_id:
            raise ValueError('reply_id cannot be empty')
        if not self.message_id:
            raise ValueError('message_id cannot be empty')
        if not self.attempt_id:
            raise ValueError('attempt_id cannot be empty')
        if not self.agent_name:
            raise ValueError('agent_name cannot be empty')
        object.__setattr__(self, 'agent_name', normalize_agent_name(self.agent_name))
        object.__setattr__(self, 'terminal_status', ReplyTerminalStatus(self.terminal_status))
        object.__setattr__(self, 'diagnostics', dict(self.diagnostics or {}))

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'reply_record',
            'reply_id': self.reply_id,
            'message_id': self.message_id,
            'attempt_id': self.attempt_id,
            'agent_name': self.agent_name,
            'terminal_status': self.terminal_status.value,
            'reply': self.reply,
            'diagnostics': dict(self.diagnostics),
            'finished_at': self.finished_at,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'ReplyRecord':
        _validate_record(record, 'reply_record')
        return cls(
            reply_id=str(record['reply_id']),
            message_id=str(record['message_id']),
            attempt_id=str(record['attempt_id']),
            agent_name=str(record['agent_name']),
            terminal_status=ReplyTerminalStatus(str(record.get('terminal_status', ReplyTerminalStatus.COMPLETED.value))),
            reply=str(record.get('reply') or ''),
            diagnostics=dict(record.get('diagnostics') or {}),
            finished_at=str(record.get('finished_at') or ''),
        )


def _validate_record(record: dict[str, Any], expected_type: str) -> None:
    if record.get('schema_version') != SCHEMA_VERSION:
        raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
    if record.get('record_type') != expected_type:
        raise ValueError(f'record_type must be {expected_type!r}')


__all__ = [
    'AttemptRecord',
    'AttemptState',
    'MessageRecord',
    'MessageState',
    'ReplyRecord',
    'ReplyTerminalStatus',
    'SCHEMA_VERSION',
]
