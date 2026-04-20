from __future__ import annotations

from typing import Any

from agents.models import normalize_agent_name
from mailbox_runtime.targets import normalize_actor_name

from .model_enums import AttemptState, MessageState, ReplyTerminalStatus, SCHEMA_VERSION


def normalize_message_record(model) -> None:
    _require_value('message_id', model.message_id)
    _require_value('from_actor', model.from_actor)
    _require_value('target_scope', model.target_scope)
    _require_agents(model.target_agents)
    _require_value('message_class', model.message_class)
    if model.priority < 0:
        raise ValueError('priority cannot be negative')
    object.__setattr__(model, 'from_actor', normalize_actor_name(model.from_actor))
    object.__setattr__(
        model,
        'target_agents',
        tuple(normalize_agent_name(agent_name) for agent_name in model.target_agents),
    )
    object.__setattr__(model, 'reply_policy', dict(model.reply_policy or {}))
    object.__setattr__(model, 'retry_policy', dict(model.retry_policy or {}))
    object.__setattr__(model, 'message_state', MessageState(model.message_state))


def message_to_record(model) -> dict[str, Any]:
    return {
        'schema_version': SCHEMA_VERSION,
        'record_type': 'message_record',
        'message_id': model.message_id,
        'origin_message_id': model.origin_message_id,
        'from_actor': model.from_actor,
        'target_scope': model.target_scope,
        'target_agents': list(model.target_agents),
        'message_class': model.message_class,
        'reply_policy': dict(model.reply_policy),
        'retry_policy': dict(model.retry_policy),
        'priority': model.priority,
        'payload_ref': model.payload_ref,
        'submission_id': model.submission_id,
        'created_at': model.created_at,
        'updated_at': model.updated_at,
        'message_state': model.message_state.value,
    }


def message_from_record(record: dict[str, Any]) -> dict[str, Any]:
    _validate_record(record, 'message_record')
    return {
        'message_id': str(record['message_id']),
        'origin_message_id': record.get('origin_message_id'),
        'from_actor': str(record['from_actor']),
        'target_scope': str(record['target_scope']),
        'target_agents': tuple(record.get('target_agents') or ()),
        'message_class': str(record.get('message_class') or 'task_request'),
        'reply_policy': dict(record.get('reply_policy') or {}),
        'retry_policy': dict(record.get('retry_policy') or {}),
        'priority': int(record.get('priority', 100)),
        'payload_ref': record.get('payload_ref'),
        'submission_id': record.get('submission_id'),
        'created_at': str(record.get('created_at') or ''),
        'updated_at': str(record.get('updated_at') or ''),
        'message_state': MessageState(str(record.get('message_state', MessageState.CREATED.value))),
    }


def normalize_attempt_record(model) -> None:
    _require_value('attempt_id', model.attempt_id)
    _require_value('message_id', model.message_id)
    _require_value('agent_name', model.agent_name)
    _require_value('provider', model.provider)
    _require_value('job_id', model.job_id)
    if model.retry_index < 0:
        raise ValueError('retry_index cannot be negative')
    object.__setattr__(model, 'agent_name', normalize_agent_name(model.agent_name))
    object.__setattr__(model, 'attempt_state', AttemptState(model.attempt_state))


def attempt_to_record(model) -> dict[str, Any]:
    return {
        'schema_version': SCHEMA_VERSION,
        'record_type': 'attempt_record',
        'attempt_id': model.attempt_id,
        'message_id': model.message_id,
        'agent_name': model.agent_name,
        'provider': model.provider,
        'job_id': model.job_id,
        'retry_index': model.retry_index,
        'health_snapshot_ref': model.health_snapshot_ref,
        'started_at': model.started_at,
        'updated_at': model.updated_at,
        'attempt_state': model.attempt_state.value,
    }


def attempt_from_record(record: dict[str, Any]) -> dict[str, Any]:
    _validate_record(record, 'attempt_record')
    return {
        'attempt_id': str(record['attempt_id']),
        'message_id': str(record['message_id']),
        'agent_name': str(record['agent_name']),
        'provider': str(record['provider']),
        'job_id': str(record['job_id']),
        'retry_index': int(record.get('retry_index', 0)),
        'health_snapshot_ref': record.get('health_snapshot_ref'),
        'started_at': str(record.get('started_at') or ''),
        'updated_at': str(record.get('updated_at') or ''),
        'attempt_state': AttemptState(str(record.get('attempt_state', AttemptState.PENDING.value))),
    }


def normalize_reply_record(model) -> None:
    _require_value('reply_id', model.reply_id)
    _require_value('message_id', model.message_id)
    _require_value('attempt_id', model.attempt_id)
    _require_value('agent_name', model.agent_name)
    object.__setattr__(model, 'agent_name', normalize_agent_name(model.agent_name))
    object.__setattr__(model, 'terminal_status', ReplyTerminalStatus(model.terminal_status))
    object.__setattr__(model, 'diagnostics', dict(model.diagnostics or {}))


def reply_to_record(model) -> dict[str, Any]:
    return {
        'schema_version': SCHEMA_VERSION,
        'record_type': 'reply_record',
        'reply_id': model.reply_id,
        'message_id': model.message_id,
        'attempt_id': model.attempt_id,
        'agent_name': model.agent_name,
        'terminal_status': model.terminal_status.value,
        'reply': model.reply,
        'diagnostics': dict(model.diagnostics),
        'finished_at': model.finished_at,
    }


def reply_from_record(record: dict[str, Any]) -> dict[str, Any]:
    _validate_record(record, 'reply_record')
    return {
        'reply_id': str(record['reply_id']),
        'message_id': str(record['message_id']),
        'attempt_id': str(record['attempt_id']),
        'agent_name': str(record['agent_name']),
        'terminal_status': ReplyTerminalStatus(
            str(record.get('terminal_status', ReplyTerminalStatus.COMPLETED.value))
        ),
        'reply': str(record.get('reply') or ''),
        'diagnostics': dict(record.get('diagnostics') or {}),
        'finished_at': str(record.get('finished_at') or ''),
    }


def _validate_record(record: dict[str, Any], expected_type: str) -> None:
    if record.get('schema_version') != SCHEMA_VERSION:
        raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
    if record.get('record_type') != expected_type:
        raise ValueError(f'record_type must be {expected_type!r}')


def _require_value(field_name: str, value: str) -> None:
    if not value:
        raise ValueError(f'{field_name} cannot be empty')


def _require_agents(target_agents) -> None:
    if not target_agents:
        raise ValueError('target_agents cannot be empty')


__all__ = [
    'attempt_from_record',
    'attempt_to_record',
    'message_from_record',
    'message_to_record',
    'normalize_attempt_record',
    'normalize_message_record',
    'normalize_reply_record',
    'reply_from_record',
    'reply_to_record',
]
