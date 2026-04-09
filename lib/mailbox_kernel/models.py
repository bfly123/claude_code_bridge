from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .model_codecs import (
    delivery_lease_from_record,
    delivery_lease_to_record,
    inbound_event_from_record,
    inbound_event_to_record,
    mailbox_from_record,
    mailbox_to_record,
    normalize_delivery_lease,
    normalize_inbound_event_record,
    normalize_mailbox_record,
)
from .model_enums import InboundEventStatus, InboundEventType, LeaseState, MailboxState, SCHEMA_VERSION


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
        normalize_mailbox_record(self)

    def to_record(self) -> dict[str, Any]:
        return mailbox_to_record(self)

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'MailboxRecord':
        return cls(**mailbox_from_record(record))


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
        normalize_inbound_event_record(self)

    def to_record(self) -> dict[str, Any]:
        return inbound_event_to_record(self)

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'InboundEventRecord':
        return cls(**inbound_event_from_record(record))


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
        normalize_delivery_lease(self)

    def to_record(self) -> dict[str, Any]:
        return delivery_lease_to_record(self)

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'DeliveryLease':
        return cls(**delivery_lease_from_record(record))


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
