from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ccbd.models_runtime.common import API_VERSION, SCHEMA_VERSION, CcbdModelError

from .cleanup import CcbdTmuxCleanupSummary
from .common import clean_text, clean_tuple, coerce_int
from .snapshots import CcbdRuntimeSnapshot


@dataclass(frozen=True)
class CcbdShutdownReport:
    project_id: str
    generated_at: str
    trigger: str
    status: str
    forced: bool
    stopped_agents: tuple[str, ...]
    daemon_generation: int | None = None
    reason: str | None = None
    inspection_after: dict[str, Any] | None = None
    actions_taken: tuple[str, ...] = ()
    cleanup_summaries: tuple[CcbdTmuxCleanupSummary, ...] = ()
    runtime_snapshots: tuple[CcbdRuntimeSnapshot, ...] = ()
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
            'record_type': 'ccbd_shutdown_report',
            'api_version': self.api_version,
            'project_id': self.project_id,
            'generated_at': self.generated_at,
            'trigger': self.trigger,
            'status': self.status,
            'forced': self.forced,
            'stopped_agents': list(self.stopped_agents),
            'daemon_generation': self.daemon_generation,
            'reason': self.reason,
            'inspection_after': dict(self.inspection_after or {}),
            'actions_taken': list(self.actions_taken),
            'cleanup_summaries': [item.to_record() for item in self.cleanup_summaries],
            'runtime_snapshots': [item.to_record() for item in self.runtime_snapshots],
            'failure_reason': self.failure_reason,
        }

    def summary_fields(self) -> dict[str, Any]:
        total_killed = sum(len(item.killed_panes) for item in self.cleanup_summaries)
        return {
            'shutdown_last_at': self.generated_at,
            'shutdown_last_trigger': self.trigger,
            'shutdown_last_status': self.status,
            'shutdown_last_forced': self.forced,
            'shutdown_last_generation': self.daemon_generation,
            'shutdown_last_reason': self.reason,
            'shutdown_last_stopped_agents': list(self.stopped_agents),
            'shutdown_last_actions': list(self.actions_taken),
            'shutdown_last_cleanup_killed': total_killed,
            'shutdown_last_failure_reason': self.failure_reason,
            'shutdown_last_runtime_states_text': runtime_snapshots_summary(self.runtime_snapshots),
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'CcbdShutdownReport':
        _validate_record(record, expected_type='ccbd_shutdown_report')
        return cls(
            project_id=str(record['project_id']),
            generated_at=str(record['generated_at']),
            trigger=str(record['trigger']),
            status=str(record['status']),
            forced=bool(record.get('forced')),
            stopped_agents=clean_tuple(record.get('stopped_agents')),
            daemon_generation=coerce_int(record.get('daemon_generation')),
            reason=clean_text(record.get('reason')),
            inspection_after=dict(record.get('inspection_after') or {}),
            actions_taken=clean_tuple(record.get('actions_taken')),
            cleanup_summaries=tuple(
                CcbdTmuxCleanupSummary.from_record(item)
                for item in (record.get('cleanup_summaries') or [])
                if isinstance(item, dict)
            ),
            runtime_snapshots=tuple(
                CcbdRuntimeSnapshot.from_record(item)
                for item in (record.get('runtime_snapshots') or [])
                if isinstance(item, dict)
            ),
            failure_reason=clean_text(record.get('failure_reason')),
            api_version=int(record.get('api_version', API_VERSION)),
        )


def runtime_snapshots_summary(items: tuple[CcbdRuntimeSnapshot, ...]) -> str:
    summaries: list[str] = []
    for item in items:
        summary = f'{item.agent_name}:{item.state}/{item.health}'
        session = item.session_id or item.session_ref or item.session_file
        extras: list[str] = []
        if item.terminal_backend:
            extras.append(f'terminal={item.terminal_backend}')
        if item.runtime_ref:
            extras.append(f'runtime={item.runtime_ref}')
        if session:
            extras.append(f'session={session}')
        if item.runtime_root:
            extras.append(f'runtime_root={item.runtime_root}')
        if item.runtime_pid is not None:
            extras.append(f'pid={item.runtime_pid}')
        if item.job_id:
            extras.append(f'job={item.job_id}')
        if item.job_owner_pid is not None:
            extras.append(f'owner={item.job_owner_pid}')
        summaries.append(summary if not extras else f'{summary} ' + ' '.join(extras))
    return '; '.join(summaries) or 'none'


def _validate_record(record: dict[str, Any], *, expected_type: str) -> None:
    if record.get('schema_version') != SCHEMA_VERSION:
        raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
    if record.get('record_type') != expected_type:
        raise ValueError(f"record_type must be '{expected_type}'")


__all__ = ['CcbdShutdownReport', 'runtime_snapshots_summary']
