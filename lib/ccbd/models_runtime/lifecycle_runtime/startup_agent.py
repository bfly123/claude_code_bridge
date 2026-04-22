from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ccbd.models_runtime.common import CcbdModelError

from .common import clean_text, coerce_int


@dataclass(frozen=True)
class CcbdStartupAgentResult:
    agent_name: str
    provider: str | None
    action: str
    health: str
    workspace_path: str | None
    runtime_ref: str | None = None
    session_ref: str | None = None
    session_file: str | None = None
    session_id: str | None = None
    lifecycle_state: str | None = None
    desired_state: str | None = None
    reconcile_state: str | None = None
    binding_source: str | None = None
    terminal_backend: str | None = None
    tmux_socket_name: str | None = None
    tmux_socket_path: str | None = None
    pane_id: str | None = None
    active_pane_id: str | None = None
    pane_state: str | None = None
    runtime_pid: int | None = None
    runtime_root: str | None = None
    job_id: str | None = None
    job_owner_pid: int | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.agent_name == '':
            raise CcbdModelError('agent_name cannot be empty')
        if self.action == '':
            raise CcbdModelError('action cannot be empty')
        if self.health == '':
            raise CcbdModelError('health cannot be empty')

    def to_record(self) -> dict[str, Any]:
        return {
            'agent_name': self.agent_name,
            'provider': self.provider,
            'action': self.action,
            'health': self.health,
            'workspace_path': self.workspace_path,
            'runtime_ref': self.runtime_ref,
            'session_ref': self.session_ref,
            'session_file': self.session_file,
            'session_id': self.session_id,
            'lifecycle_state': self.lifecycle_state,
            'desired_state': self.desired_state,
            'reconcile_state': self.reconcile_state,
            'binding_source': self.binding_source,
            'terminal_backend': self.terminal_backend,
            'tmux_socket_name': self.tmux_socket_name,
            'tmux_socket_path': self.tmux_socket_path,
            'pane_id': self.pane_id,
            'active_pane_id': self.active_pane_id,
            'pane_state': self.pane_state,
            'runtime_pid': self.runtime_pid,
            'runtime_root': self.runtime_root,
            'job_id': self.job_id,
            'job_owner_pid': self.job_owner_pid,
            'failure_reason': self.failure_reason,
        }

    def summary_token(self) -> str:
        summary = f'{self.agent_name}:{self.action}/{self.health}'
        session = self.session_id or self.session_ref or self.session_file
        extras: list[str] = []
        if self.terminal_backend:
            extras.append(f'terminal={self.terminal_backend}')
        if self.runtime_ref:
            extras.append(f'runtime={self.runtime_ref}')
        if session:
            extras.append(f'session={session}')
        if self.runtime_root:
            extras.append(f'runtime_root={self.runtime_root}')
        if self.runtime_pid is not None:
            extras.append(f'pid={self.runtime_pid}')
        if self.job_id:
            extras.append(f'job={self.job_id}')
        if self.job_owner_pid is not None:
            extras.append(f'owner={self.job_owner_pid}')
        return summary if not extras else f'{summary} ' + ' '.join(extras)

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'CcbdStartupAgentResult':
        return cls(
            agent_name=clean_text(record.get('agent_name')) or '',
            provider=clean_text(record.get('provider')),
            action=clean_text(record.get('action')) or 'unknown',
            health=clean_text(record.get('health')) or 'unknown',
            workspace_path=clean_text(record.get('workspace_path')),
            runtime_ref=clean_text(record.get('runtime_ref')),
            session_ref=clean_text(record.get('session_ref')),
            session_file=clean_text(record.get('session_file')),
            session_id=clean_text(record.get('session_id')),
            lifecycle_state=clean_text(record.get('lifecycle_state')),
            desired_state=clean_text(record.get('desired_state')),
            reconcile_state=clean_text(record.get('reconcile_state')),
            binding_source=clean_text(record.get('binding_source')),
            terminal_backend=clean_text(record.get('terminal_backend')),
            tmux_socket_name=clean_text(record.get('tmux_socket_name')),
            tmux_socket_path=clean_text(record.get('tmux_socket_path')),
            pane_id=clean_text(record.get('pane_id')),
            active_pane_id=clean_text(record.get('active_pane_id')),
            pane_state=clean_text(record.get('pane_state')),
            runtime_pid=coerce_int(record.get('runtime_pid')),
            runtime_root=clean_text(record.get('runtime_root')),
            job_id=clean_text(record.get('job_id')),
            job_owner_pid=coerce_int(record.get('job_owner_pid')),
            failure_reason=clean_text(record.get('failure_reason')),
        )


__all__ = ['CcbdStartupAgentResult']
