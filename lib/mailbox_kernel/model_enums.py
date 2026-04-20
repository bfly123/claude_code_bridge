from __future__ import annotations

from enum import Enum

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


__all__ = [
    'InboundEventStatus',
    'InboundEventType',
    'LeaseState',
    'MailboxState',
    'SCHEMA_VERSION',
]
