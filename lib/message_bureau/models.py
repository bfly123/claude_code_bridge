from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model_codecs import (
    attempt_from_record,
    attempt_to_record,
    message_from_record,
    message_to_record,
    normalize_attempt_record,
    normalize_message_record,
    normalize_reply_record,
    reply_from_record,
    reply_to_record,
)
from .model_enums import AttemptState, MessageState, ReplyTerminalStatus, SCHEMA_VERSION


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
        normalize_message_record(self)

    def to_record(self) -> dict[str, Any]:
        return message_to_record(self)

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'MessageRecord':
        return cls(**message_from_record(record))


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
        normalize_attempt_record(self)

    def to_record(self) -> dict[str, Any]:
        return attempt_to_record(self)

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'AttemptRecord':
        return cls(**attempt_from_record(record))


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
        normalize_reply_record(self)

    def to_record(self) -> dict[str, Any]:
        return reply_to_record(self)

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'ReplyRecord':
        return cls(**reply_from_record(record))


__all__ = [
    'AttemptRecord',
    'AttemptState',
    'MessageRecord',
    'MessageState',
    'ReplyRecord',
    'ReplyTerminalStatus',
    'SCHEMA_VERSION',
]
