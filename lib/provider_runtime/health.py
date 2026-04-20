from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agents.models import normalize_agent_name

SCHEMA_VERSION = 1


class ProgressState(str, Enum):
    NOT_STARTED = 'not_started'
    SUBMITTED = 'submitted'
    ACCEPTED = 'accepted'
    ACTIVELY_RUNNING = 'actively_running'
    QUIET_WAIT = 'quiet_wait'
    OUTPUT_ADVANCING = 'output_advancing'
    STALLED = 'stalled'
    RUNTIME_LOST = 'runtime_lost'
    SESSION_LOST = 'session_lost'
    UNKNOWN = 'unknown'


class ProviderCompletionState(str, Enum):
    NOT_COMPLETE = 'not_complete'
    TERMINAL_COMPLETE = 'terminal_complete'
    TERMINAL_INCOMPLETE = 'terminal_incomplete'
    TERMINAL_FAILED = 'terminal_failed'
    TERMINAL_CANCELLED = 'terminal_cancelled'
    INDETERMINATE = 'indeterminate'


@dataclass(frozen=True)
class ProviderHealthSnapshot:
    job_id: str
    provider: str
    agent_name: str
    runtime_alive: bool
    session_reachable: bool | None
    progress_state: ProgressState
    completion_state: ProviderCompletionState
    last_progress_at: str | None
    observed_at: str
    degraded_reason: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError('job_id cannot be empty')
        if not self.provider:
            raise ValueError('provider cannot be empty')
        if not self.agent_name:
            raise ValueError('agent_name cannot be empty')
        object.__setattr__(self, 'agent_name', normalize_agent_name(self.agent_name))
        object.__setattr__(self, 'progress_state', ProgressState(self.progress_state))
        object.__setattr__(self, 'completion_state', ProviderCompletionState(self.completion_state))
        object.__setattr__(self, 'diagnostics', dict(self.diagnostics or {}))

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'provider_health_snapshot',
            'job_id': self.job_id,
            'provider': self.provider,
            'agent_name': self.agent_name,
            'runtime_alive': self.runtime_alive,
            'session_reachable': self.session_reachable,
            'progress_state': self.progress_state.value,
            'completion_state': self.completion_state.value,
            'last_progress_at': self.last_progress_at,
            'observed_at': self.observed_at,
            'degraded_reason': self.degraded_reason,
            'diagnostics': dict(self.diagnostics),
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'ProviderHealthSnapshot':
        _validate_record(record, 'provider_health_snapshot')
        return cls(
            job_id=str(record['job_id']),
            provider=str(record['provider']),
            agent_name=str(record['agent_name']),
            runtime_alive=bool(record.get('runtime_alive', False)),
            session_reachable=record.get('session_reachable'),
            progress_state=ProgressState(str(record.get('progress_state', ProgressState.UNKNOWN.value))),
            completion_state=ProviderCompletionState(
                str(record.get('completion_state', ProviderCompletionState.INDETERMINATE.value))
            ),
            last_progress_at=record.get('last_progress_at'),
            observed_at=str(record.get('observed_at') or ''),
            degraded_reason=record.get('degraded_reason'),
            diagnostics=dict(record.get('diagnostics') or {}),
        )


def _validate_record(record: dict[str, Any], expected_type: str) -> None:
    if record.get('schema_version') != SCHEMA_VERSION:
        raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
    if record.get('record_type') != expected_type:
        raise ValueError(f'record_type must be {expected_type!r}')


__all__ = [
    'ProgressState',
    'ProviderCompletionState',
    'ProviderHealthSnapshot',
    'SCHEMA_VERSION',
]
