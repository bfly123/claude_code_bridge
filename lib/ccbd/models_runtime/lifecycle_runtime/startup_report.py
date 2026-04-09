from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ccbd.models_runtime.common import API_VERSION, SCHEMA_VERSION, CcbdModelError

from .cleanup import CcbdTmuxCleanupSummary
from .common import clean_text, clean_tuple, coerce_int
from .startup_agent import CcbdStartupAgentResult


@dataclass(frozen=True)
class CcbdStartupReport:
    project_id: str
    generated_at: str
    trigger: str
    status: str
    requested_agents: tuple[str, ...]
    desired_agents: tuple[str, ...]
    restore_requested: bool
    auto_permission: bool
    daemon_generation: int | None = None
    daemon_started: bool | None = None
    config_signature: str | None = None
    inspection: dict[str, Any] | None = None
    restore_summary: dict[str, Any] | None = None
    actions_taken: tuple[str, ...] = ()
    cleanup_summaries: tuple[CcbdTmuxCleanupSummary, ...] = ()
    agent_results: tuple[CcbdStartupAgentResult, ...] = ()
    failure_reason: str | None = None
    api_version: int = API_VERSION

    def __post_init__(self) -> None:
        if self.api_version != API_VERSION:
            raise CcbdModelError(f'api_version must be {API_VERSION}')
        for field_name in ('project_id', 'generated_at', 'trigger', 'status'):
            if not str(getattr(self, field_name) or '').strip():
                raise CcbdModelError(f'{field_name} cannot be empty')

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'ccbd_startup_report',
            'api_version': self.api_version,
            'project_id': self.project_id,
            'generated_at': self.generated_at,
            'trigger': self.trigger,
            'status': self.status,
            'requested_agents': list(self.requested_agents),
            'desired_agents': list(self.desired_agents),
            'restore_requested': self.restore_requested,
            'auto_permission': self.auto_permission,
            'daemon_generation': self.daemon_generation,
            'daemon_started': self.daemon_started,
            'config_signature': self.config_signature,
            'inspection': dict(self.inspection or {}),
            'restore_summary': dict(self.restore_summary or {}),
            'actions_taken': list(self.actions_taken),
            'cleanup_summaries': [item.to_record() for item in self.cleanup_summaries],
            'agent_results': [item.to_record() for item in self.agent_results],
            'failure_reason': self.failure_reason,
        }

    def summary_fields(self) -> dict[str, Any]:
        total_killed = sum(len(item.killed_panes) for item in self.cleanup_summaries)
        return {
            'startup_last_at': self.generated_at,
            'startup_last_trigger': self.trigger,
            'startup_last_status': self.status,
            'startup_last_generation': self.daemon_generation,
            'startup_last_daemon_started': self.daemon_started,
            'startup_last_requested_agents': list(self.requested_agents),
            'startup_last_desired_agents': list(self.desired_agents),
            'startup_last_actions': list(self.actions_taken),
            'startup_last_cleanup_killed': total_killed,
            'startup_last_failure_reason': self.failure_reason,
            'startup_last_agent_results_text': 'none'
            if not self.agent_results
            else '; '.join(item.summary_token() for item in self.agent_results),
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'CcbdStartupReport':
        _validate_record(record, expected_type='ccbd_startup_report')
        return cls(
            project_id=str(record['project_id']),
            generated_at=str(record['generated_at']),
            trigger=str(record['trigger']),
            status=str(record['status']),
            requested_agents=clean_tuple(record.get('requested_agents')),
            desired_agents=clean_tuple(record.get('desired_agents')),
            restore_requested=bool(record.get('restore_requested')),
            auto_permission=bool(record.get('auto_permission')),
            daemon_generation=coerce_int(record.get('daemon_generation')),
            daemon_started=(bool(record['daemon_started']) if record.get('daemon_started') is not None else None),
            config_signature=clean_text(record.get('config_signature')),
            inspection=dict(record.get('inspection') or {}),
            restore_summary=dict(record.get('restore_summary') or {}),
            actions_taken=clean_tuple(record.get('actions_taken')),
            cleanup_summaries=tuple(
                CcbdTmuxCleanupSummary.from_record(item)
                for item in (record.get('cleanup_summaries') or [])
                if isinstance(item, dict)
            ),
            agent_results=tuple(
                CcbdStartupAgentResult.from_record(item)
                for item in (record.get('agent_results') or [])
                if isinstance(item, dict)
            ),
            failure_reason=clean_text(record.get('failure_reason')),
            api_version=int(record.get('api_version', API_VERSION)),
        )


def _validate_record(record: dict[str, Any], *, expected_type: str) -> None:
    if record.get('schema_version') != SCHEMA_VERSION:
        raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
    if record.get('record_type') != expected_type:
        raise ValueError(f"record_type must be '{expected_type}'")


__all__ = ['CcbdStartupReport']
