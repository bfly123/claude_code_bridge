from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ccbd.models_runtime.common import CcbdModelError

from .common import clean_text, coerce_int, to_runtime_state


@dataclass(frozen=True)
class CcbdRuntimeSnapshot:
    agent_name: str
    provider: str | None
    state: str | None
    health: str
    workspace_path: str | None
    runtime_ref: str | None = None
    session_ref: str | None = None
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
    last_failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.agent_name == '':
            raise CcbdModelError('agent_name cannot be empty')
        if self.health == '':
            raise CcbdModelError('health cannot be empty')

    def to_record(self) -> dict[str, Any]:
        return {
            'agent_name': self.agent_name,
            'provider': self.provider,
            'state': self.state,
            'health': self.health,
            'workspace_path': self.workspace_path,
            'runtime_ref': self.runtime_ref,
            'session_ref': self.session_ref,
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
            'last_failure_reason': self.last_failure_reason,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'CcbdRuntimeSnapshot':
        return cls(
            agent_name=clean_text(record.get('agent_name')) or '',
            provider=clean_text(record.get('provider')),
            state=clean_text(record.get('state')),
            health=clean_text(record.get('health')) or 'unknown',
            workspace_path=clean_text(record.get('workspace_path')),
            runtime_ref=clean_text(record.get('runtime_ref')),
            session_ref=clean_text(record.get('session_ref')),
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
            last_failure_reason=clean_text(record.get('last_failure_reason')),
        )

    @classmethod
    def from_runtime(cls, runtime) -> 'CcbdRuntimeSnapshot':
        return cls(
            agent_name=clean_text(getattr(runtime, 'agent_name', None)) or '',
            provider=clean_text(getattr(runtime, 'provider', None)),
            state=to_runtime_state(getattr(runtime, 'state', None)),
            health=clean_text(getattr(runtime, 'health', None)) or 'unknown',
            workspace_path=clean_text(getattr(runtime, 'workspace_path', None)),
            runtime_ref=clean_text(getattr(runtime, 'runtime_ref', None)),
            session_ref=clean_text(getattr(runtime, 'session_ref', None)),
            lifecycle_state=clean_text(getattr(runtime, 'lifecycle_state', None)),
            desired_state=clean_text(getattr(runtime, 'desired_state', None)),
            reconcile_state=clean_text(getattr(runtime, 'reconcile_state', None)),
            binding_source=to_runtime_state(getattr(runtime, 'binding_source', None)),
            terminal_backend=clean_text(getattr(runtime, 'terminal_backend', None)),
            tmux_socket_name=clean_text(getattr(runtime, 'tmux_socket_name', None)),
            tmux_socket_path=clean_text(getattr(runtime, 'tmux_socket_path', None)),
            pane_id=clean_text(getattr(runtime, 'pane_id', None)),
            active_pane_id=clean_text(getattr(runtime, 'active_pane_id', None)),
            pane_state=clean_text(getattr(runtime, 'pane_state', None)),
            runtime_pid=coerce_int(getattr(runtime, 'runtime_pid', None)),
            runtime_root=clean_text(getattr(runtime, 'runtime_root', None)),
            last_failure_reason=clean_text(getattr(runtime, 'last_failure_reason', None)),
        )


__all__ = ['CcbdRuntimeSnapshot']
