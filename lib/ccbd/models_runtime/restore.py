from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .common import API_VERSION, SCHEMA_VERSION, CcbdModelError


@dataclass(frozen=True)
class CcbdRestoreEntry:
    job_id: str
    agent_name: str
    provider: str
    status: str
    reason: str
    resume_capable: bool
    pending_items_count: int = 0

    def __post_init__(self) -> None:
        if not (self.job_id or '').strip():
            raise CcbdModelError('job_id cannot be empty')
        if not (self.agent_name or '').strip():
            raise CcbdModelError('agent_name cannot be empty')
        if not (self.provider or '').strip():
            raise CcbdModelError('provider cannot be empty')
        if not (self.status or '').strip():
            raise CcbdModelError('status cannot be empty')
        if not (self.reason or '').strip():
            raise CcbdModelError('reason cannot be empty')
        if self.pending_items_count < 0:
            raise CcbdModelError('pending_items_count cannot be negative')

    def to_record(self) -> dict[str, Any]:
        return {
            'job_id': self.job_id,
            'agent_name': self.agent_name,
            'provider': self.provider,
            'status': self.status,
            'reason': self.reason,
            'resume_capable': self.resume_capable,
            'pending_items_count': self.pending_items_count,
        }

    def summary_token(self) -> str:
        pending_suffix = ''
        if self.pending_items_count > 0:
            pending_suffix = f',pending_items={self.pending_items_count}'
        return f'{self.agent_name}/{self.provider}:{self.status}({self.reason}{pending_suffix})'


@dataclass(frozen=True)
class CcbdRestoreReport:
    project_id: str
    generated_at: str
    running_job_count: int
    restored_execution_count: int
    replay_pending_count: int
    terminal_pending_count: int
    abandoned_execution_count: int
    already_active_count: int
    entries: tuple[CcbdRestoreEntry, ...] = ()
    api_version: int = API_VERSION

    def __post_init__(self) -> None:
        if self.api_version != API_VERSION:
            raise CcbdModelError(f'api_version must be {API_VERSION}')
        if not (self.project_id or '').strip():
            raise CcbdModelError('project_id cannot be empty')
        if not (self.generated_at or '').strip():
            raise CcbdModelError('generated_at cannot be empty')
        for field_name in (
            'running_job_count',
            'restored_execution_count',
            'replay_pending_count',
            'terminal_pending_count',
            'abandoned_execution_count',
            'already_active_count',
        ):
            if getattr(self, field_name) < 0:
                raise CcbdModelError(f'{field_name} cannot be negative')

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'ccbd_restore_report',
            'api_version': self.api_version,
            'project_id': self.project_id,
            'generated_at': self.generated_at,
            'running_job_count': self.running_job_count,
            'restored_execution_count': self.restored_execution_count,
            'replay_pending_count': self.replay_pending_count,
            'terminal_pending_count': self.terminal_pending_count,
            'abandoned_execution_count': self.abandoned_execution_count,
            'already_active_count': self.already_active_count,
            'entries': [entry.to_record() for entry in self.entries],
        }

    def summary_fields(self) -> dict[str, Any]:
        return {
            'last_restore_at': self.generated_at,
            'last_restore_running_job_count': self.running_job_count,
            'last_restore_restored_execution_count': self.restored_execution_count,
            'last_restore_replay_pending_count': self.replay_pending_count,
            'last_restore_terminal_pending_count': self.terminal_pending_count,
            'last_restore_abandoned_execution_count': self.abandoned_execution_count,
            'last_restore_already_active_count': self.already_active_count,
            'last_restore_results_text': 'none' if not self.entries else '; '.join(entry.summary_token() for entry in self.entries),
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'CcbdRestoreReport':
        if record.get('schema_version') != SCHEMA_VERSION:
            raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
        if record.get('record_type') != 'ccbd_restore_report':
            raise ValueError("record_type must be 'ccbd_restore_report'")
        return cls(
            project_id=str(record['project_id']),
            generated_at=str(record['generated_at']),
            running_job_count=int(record.get('running_job_count', 0)),
            restored_execution_count=int(record.get('restored_execution_count', 0)),
            replay_pending_count=int(record.get('replay_pending_count', 0)),
            terminal_pending_count=int(record.get('terminal_pending_count', 0)),
            abandoned_execution_count=int(record.get('abandoned_execution_count', 0)),
            already_active_count=int(record.get('already_active_count', 0)),
            entries=tuple(
                CcbdRestoreEntry(
                    job_id=str(entry['job_id']),
                    agent_name=str(entry['agent_name']),
                    provider=str(entry['provider']),
                    status=str(entry['status']),
                    reason=str(entry['reason']),
                    resume_capable=bool(entry.get('resume_capable', False)),
                    pending_items_count=int(entry.get('pending_items_count', 0)),
                )
                for entry in record.get('entries', [])
            ),
            api_version=int(record.get('api_version', API_VERSION)),
        )


__all__ = ['CcbdRestoreEntry', 'CcbdRestoreReport']
