from __future__ import annotations

from typing import Any

from mailbox_runtime.targets import normalize_mailbox_owner_name

from .model_enums import InboundEventStatus, InboundEventType, LeaseState, MailboxState, SCHEMA_VERSION


def normalize_mailbox_record(record) -> None:
    if not record.mailbox_id:
        raise ValueError('mailbox_id cannot be empty')
    if not record.agent_name:
        raise ValueError('agent_name cannot be empty')
    if record.queue_depth < 0:
        raise ValueError('queue_depth cannot be negative')
    if record.pending_reply_count < 0:
        raise ValueError('pending_reply_count cannot be negative')
    if record.lease_version < 0:
        raise ValueError('lease_version cannot be negative')
    object.__setattr__(record, 'agent_name', normalize_mailbox_owner_name(record.agent_name))
    object.__setattr__(record, 'mailbox_state', MailboxState(record.mailbox_state))


def mailbox_to_record(record) -> dict[str, Any]:
    return {
        'schema_version': SCHEMA_VERSION,
        'record_type': 'mailbox_record',
        'mailbox_id': record.mailbox_id,
        'agent_name': record.agent_name,
        'active_inbound_event_id': record.active_inbound_event_id,
        'queue_depth': record.queue_depth,
        'pending_reply_count': record.pending_reply_count,
        'last_inbound_started_at': record.last_inbound_started_at,
        'last_inbound_finished_at': record.last_inbound_finished_at,
        'mailbox_state': record.mailbox_state.value,
        'lease_version': record.lease_version,
        'updated_at': record.updated_at,
    }


def mailbox_from_record(record: dict[str, Any]) -> dict[str, Any]:
    _validate_record(record, 'mailbox_record')
    return {
        'mailbox_id': str(record['mailbox_id']),
        'agent_name': str(record['agent_name']),
        'active_inbound_event_id': record.get('active_inbound_event_id'),
        'queue_depth': int(record.get('queue_depth', 0)),
        'pending_reply_count': int(record.get('pending_reply_count', 0)),
        'last_inbound_started_at': record.get('last_inbound_started_at'),
        'last_inbound_finished_at': record.get('last_inbound_finished_at'),
        'mailbox_state': MailboxState(str(record.get('mailbox_state', MailboxState.IDLE.value))),
        'lease_version': int(record.get('lease_version', 0)),
        'updated_at': str(record.get('updated_at') or ''),
    }


def normalize_inbound_event_record(record) -> None:
    if not record.inbound_event_id:
        raise ValueError('inbound_event_id cannot be empty')
    if not record.agent_name:
        raise ValueError('agent_name cannot be empty')
    if not record.message_id:
        raise ValueError('message_id cannot be empty')
    if record.priority < 0:
        raise ValueError('priority cannot be negative')
    object.__setattr__(record, 'agent_name', normalize_mailbox_owner_name(record.agent_name))
    object.__setattr__(record, 'event_type', InboundEventType(record.event_type))
    object.__setattr__(record, 'status', InboundEventStatus(record.status))


def inbound_event_to_record(record) -> dict[str, Any]:
    return {
        'schema_version': SCHEMA_VERSION,
        'record_type': 'inbound_event_record',
        'inbound_event_id': record.inbound_event_id,
        'agent_name': record.agent_name,
        'event_type': record.event_type.value,
        'message_id': record.message_id,
        'attempt_id': record.attempt_id,
        'payload_ref': record.payload_ref,
        'priority': record.priority,
        'status': record.status.value,
        'created_at': record.created_at,
        'started_at': record.started_at,
        'finished_at': record.finished_at,
    }


def inbound_event_from_record(record: dict[str, Any]) -> dict[str, Any]:
    _validate_record(record, 'inbound_event_record')
    return {
        'inbound_event_id': str(record['inbound_event_id']),
        'agent_name': str(record['agent_name']),
        'event_type': InboundEventType(str(record['event_type'])),
        'message_id': str(record['message_id']),
        'attempt_id': record.get('attempt_id'),
        'payload_ref': record.get('payload_ref'),
        'priority': int(record.get('priority', 0)),
        'status': InboundEventStatus(str(record.get('status', InboundEventStatus.QUEUED.value))),
        'created_at': str(record.get('created_at') or ''),
        'started_at': record.get('started_at'),
        'finished_at': record.get('finished_at'),
    }


def normalize_delivery_lease(record) -> None:
    if not record.agent_name:
        raise ValueError('agent_name cannot be empty')
    if not record.inbound_event_id:
        raise ValueError('inbound_event_id cannot be empty')
    if record.lease_version < 0:
        raise ValueError('lease_version cannot be negative')
    object.__setattr__(record, 'agent_name', normalize_mailbox_owner_name(record.agent_name))
    object.__setattr__(record, 'lease_state', LeaseState(record.lease_state))


def delivery_lease_to_record(record) -> dict[str, Any]:
    return {
        'schema_version': SCHEMA_VERSION,
        'record_type': 'delivery_lease',
        'agent_name': record.agent_name,
        'inbound_event_id': record.inbound_event_id,
        'lease_version': record.lease_version,
        'acquired_at': record.acquired_at,
        'last_progress_at': record.last_progress_at,
        'expires_at': record.expires_at,
        'lease_state': record.lease_state.value,
    }


def delivery_lease_from_record(record: dict[str, Any]) -> dict[str, Any]:
    _validate_record(record, 'delivery_lease')
    return {
        'agent_name': str(record['agent_name']),
        'inbound_event_id': str(record['inbound_event_id']),
        'lease_version': int(record.get('lease_version', 0)),
        'acquired_at': str(record.get('acquired_at') or ''),
        'last_progress_at': record.get('last_progress_at'),
        'expires_at': record.get('expires_at'),
        'lease_state': LeaseState(str(record.get('lease_state', LeaseState.ACQUIRED.value))),
    }


def _validate_record(record: dict[str, Any], expected_type: str) -> None:
    if record.get('schema_version') != SCHEMA_VERSION:
        raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
    if record.get('record_type') != expected_type:
        raise ValueError(f'record_type must be {expected_type!r}')


__all__ = [
    'delivery_lease_from_record',
    'delivery_lease_to_record',
    'inbound_event_from_record',
    'inbound_event_to_record',
    'mailbox_from_record',
    'mailbox_to_record',
    'normalize_delivery_lease',
    'normalize_inbound_event_record',
    'normalize_mailbox_record',
]
