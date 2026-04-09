from __future__ import annotations

from enum import Enum

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


__all__ = [
    'AttemptState',
    'MessageState',
    'ReplyTerminalStatus',
    'SCHEMA_VERSION',
]
