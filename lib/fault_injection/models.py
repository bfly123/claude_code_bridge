from __future__ import annotations

from dataclasses import dataclass

from agents.models import normalize_agent_name

SCHEMA_VERSION = 1
VALID_FAILURE_REASONS = frozenset({'api_error', 'transport_error'})


@dataclass(frozen=True)
class FaultRule:
    rule_id: str
    agent_name: str
    task_id: str
    reason: str
    remaining_count: int
    error_message: str
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        if not str(self.rule_id or '').strip():
            raise ValueError('rule_id cannot be empty')
        if not str(self.task_id or '').strip():
            raise ValueError('task_id cannot be empty')
        if int(self.remaining_count) <= 0:
            raise ValueError('remaining_count must be positive')
        normalized_agent = normalize_agent_name(self.agent_name)
        reason = str(self.reason or '').strip().lower()
        if reason not in VALID_FAILURE_REASONS:
            raise ValueError(f'unsupported fault reason: {self.reason}')
        object.__setattr__(self, 'agent_name', normalized_agent)
        object.__setattr__(self, 'task_id', str(self.task_id).strip())
        object.__setattr__(self, 'reason', reason)
        object.__setattr__(self, 'remaining_count', int(self.remaining_count))
        object.__setattr__(self, 'error_message', str(self.error_message or '').strip())

    def to_record(self) -> dict[str, object]:
        return {
            'rule_id': self.rule_id,
            'agent_name': self.agent_name,
            'task_id': self.task_id,
            'reason': self.reason,
            'remaining_count': self.remaining_count,
            'error_message': self.error_message,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_record(cls, record: dict[str, object]) -> 'FaultRule':
        return cls(
            rule_id=str(record.get('rule_id') or ''),
            agent_name=str(record.get('agent_name') or ''),
            task_id=str(record.get('task_id') or ''),
            reason=str(record.get('reason') or ''),
            remaining_count=int(record.get('remaining_count') or 0),
            error_message=str(record.get('error_message') or ''),
            created_at=str(record.get('created_at') or ''),
            updated_at=str(record.get('updated_at') or ''),
        )


__all__ = ['FaultRule', 'SCHEMA_VERSION', 'VALID_FAILURE_REASONS']
