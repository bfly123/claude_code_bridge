from __future__ import annotations

from dataclasses import dataclass

from storage.jsonl_store import JsonlStore
from storage.paths import PathLayout

_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SupervisionEvent:
    event_kind: str
    project_id: str
    agent_name: str
    occurred_at: str
    daemon_generation: int | None = None
    desired_state: str | None = None
    reconcile_state: str | None = None
    prior_health: str | None = None
    result_health: str | None = None
    runtime_state: str | None = None
    runtime_ref: str | None = None
    session_ref: str | None = None
    details: dict[str, object] | None = None

    def to_record(self) -> dict[str, object]:
        return {
            'schema_version': _SCHEMA_VERSION,
            'record_type': 'ccbd_supervision_event',
            'event_kind': self.event_kind,
            'project_id': self.project_id,
            'agent_name': self.agent_name,
            'occurred_at': self.occurred_at,
            'daemon_generation': self.daemon_generation,
            'desired_state': self.desired_state,
            'reconcile_state': self.reconcile_state,
            'prior_health': self.prior_health,
            'result_health': self.result_health,
            'runtime_state': self.runtime_state,
            'runtime_ref': self.runtime_ref,
            'session_ref': self.session_ref,
            'details': dict(self.details or {}),
        }

    @classmethod
    def from_record(cls, record: dict[str, object]) -> SupervisionEvent:
        if int(record.get('schema_version') or 0) != _SCHEMA_VERSION:
            raise ValueError('invalid schema_version for supervision event')
        if record.get('record_type') != 'ccbd_supervision_event':
            raise ValueError('invalid record_type for supervision event')
        generation = record.get('daemon_generation')
        return cls(
            event_kind=_clean_text(record.get('event_kind')) or 'unknown',
            project_id=_clean_text(record.get('project_id')) or '',
            agent_name=_clean_text(record.get('agent_name')) or '',
            occurred_at=_clean_text(record.get('occurred_at')) or '',
            daemon_generation=int(generation) if generation is not None else None,
            desired_state=_clean_text(record.get('desired_state')),
            reconcile_state=_clean_text(record.get('reconcile_state')),
            prior_health=_clean_text(record.get('prior_health')),
            result_health=_clean_text(record.get('result_health')),
            runtime_state=_clean_text(record.get('runtime_state')),
            runtime_ref=_clean_text(record.get('runtime_ref')),
            session_ref=_clean_text(record.get('session_ref')),
            details=dict(record.get('details') or {}),
        )


class SupervisionEventStore:
    def __init__(self, layout: PathLayout, store: JsonlStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonlStore()

    def append(self, event: SupervisionEvent) -> None:
        self._store.append(self._layout.ccbd_supervision_path, event, serializer=lambda value: value.to_record())

    def read_all(self) -> list[SupervisionEvent]:
        return self._store.read_all(self._layout.ccbd_supervision_path, loader=SupervisionEvent.from_record)


def _clean_text(value: object) -> str | None:
    text = str(value or '').strip()
    return text or None


__all__ = ['SupervisionEvent', 'SupervisionEventStore']
