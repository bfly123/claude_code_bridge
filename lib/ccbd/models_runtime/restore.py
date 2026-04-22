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
    runtime_ref: str | None = None
    session_ref: str | None = None
    session_file: str | None = None
    session_id: str | None = None
    terminal_backend: str | None = None
    runtime_root: str | None = None
    runtime_pid: int | None = None
    runtime_job_id: str | None = None
    job_owner_pid: int | None = None

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
            'runtime_ref': self.runtime_ref,
            'session_ref': self.session_ref,
            'session_file': self.session_file,
            'session_id': self.session_id,
            'terminal_backend': self.terminal_backend,
            'runtime_root': self.runtime_root,
            'runtime_pid': self.runtime_pid,
            'runtime_job_id': self.runtime_job_id,
            'job_owner_pid': self.job_owner_pid,
        }

    def summary_token(self) -> str:
        pending_suffix = ''
        if self.pending_items_count > 0:
            pending_suffix = f',pending_items={self.pending_items_count}'
        extras: list[str] = []
        if self.terminal_backend:
            extras.append(f'terminal={self.terminal_backend}')
        if self.runtime_ref:
            extras.append(f'runtime={self.runtime_ref}')
        session_ref = self.session_id or self.session_ref or self.session_file
        if session_ref:
            extras.append(f'session={session_ref}')
        if self.runtime_root:
            extras.append(f'runtime_root={self.runtime_root}')
        if self.runtime_pid is not None:
            extras.append(f'pid={self.runtime_pid}')
        if self.runtime_job_id:
            extras.append(f'job={self.runtime_job_id}')
        if self.job_owner_pid is not None:
            extras.append(f'owner={self.job_owner_pid}')
        suffix = '' if not extras else f' {" ".join(extras)}'
        return f'{self.agent_name}/{self.provider}:{self.status}({self.reason}{pending_suffix}){suffix}'


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
                    runtime_ref=_optional_text(entry.get('runtime_ref')),
                    session_ref=_optional_text(entry.get('session_ref')),
                    session_file=_optional_text(entry.get('session_file')),
                    session_id=_optional_text(entry.get('session_id')),
                    terminal_backend=_optional_text(entry.get('terminal_backend')),
                    runtime_root=_optional_text(entry.get('runtime_root')),
                    runtime_pid=_optional_int(entry.get('runtime_pid')),
                    runtime_job_id=_optional_text(entry.get('runtime_job_id')),
                    job_owner_pid=_optional_int(entry.get('job_owner_pid')),
                )
                for entry in record.get('entries', [])
            ),
            api_version=int(record.get('api_version', API_VERSION)),
        )


def _optional_text(value: object) -> str | None:
    text = str(value or '').strip()
    return text or None


def _optional_int(value: object) -> int | None:
    if value is None or value == '':
        return None
    number = int(value)
    return number if number > 0 else None


__all__ = ['CcbdRestoreEntry', 'CcbdRestoreReport']
