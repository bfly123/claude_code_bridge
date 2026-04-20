from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.models_runtime.enums import AgentState, RuntimeBindingSource
from agents.models_runtime.names import SCHEMA_VERSION, normalize_agent_name

from .helpers import normalize_runtime_defaults, validate_runtime_fields


@dataclass
class AgentRuntime:
    agent_name: str
    state: AgentState
    pid: int | None
    started_at: str | None
    last_seen_at: str | None
    runtime_ref: str | None
    session_ref: str | None
    workspace_path: str | None
    project_id: str
    backend_type: str
    queue_depth: int
    socket_path: str | None
    health: str
    provider: str | None = None
    runtime_root: str | None = None
    runtime_pid: int | None = None
    terminal_backend: str | None = None
    pane_id: str | None = None
    active_pane_id: str | None = None
    pane_title_marker: str | None = None
    pane_state: str | None = None
    tmux_socket_name: str | None = None
    tmux_socket_path: str | None = None
    session_file: str | None = None
    session_id: str | None = None
    slot_key: str | None = None
    window_id: str | None = None
    workspace_epoch: int | None = None
    lifecycle_state: str | None = None
    binding_generation: int = 1
    managed_by: str = 'ccbd'
    binding_source: RuntimeBindingSource = RuntimeBindingSource.PROVIDER_SESSION
    daemon_generation: int | None = None
    desired_state: str | None = None
    reconcile_state: str | None = None
    restart_count: int = 0
    last_reconcile_at: str | None = None
    last_failure_reason: str | None = None

    def __post_init__(self) -> None:
        self.agent_name = normalize_agent_name(self.agent_name)
        validate_runtime_fields(self)
        normalize_runtime_defaults(self)

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'agent_runtime',
            'agent_name': self.agent_name,
            'state': self.state.value,
            'pid': self.pid,
            'started_at': self.started_at,
            'last_seen_at': self.last_seen_at,
            'runtime_ref': self.runtime_ref,
            'session_ref': self.session_ref,
            'workspace_path': self.workspace_path,
            'project_id': self.project_id,
            'backend_type': self.backend_type,
            'queue_depth': self.queue_depth,
            'socket_path': self.socket_path,
            'health': self.health,
            'provider': self.provider,
            'runtime_root': self.runtime_root,
            'runtime_pid': self.runtime_pid,
            'terminal_backend': self.terminal_backend,
            'pane_id': self.pane_id,
            'active_pane_id': self.active_pane_id,
            'pane_title_marker': self.pane_title_marker,
            'pane_state': self.pane_state,
            'tmux_socket_name': self.tmux_socket_name,
            'tmux_socket_path': self.tmux_socket_path,
            'session_file': self.session_file,
            'session_id': self.session_id,
            'slot_key': self.slot_key,
            'window_id': self.window_id,
            'workspace_epoch': self.workspace_epoch,
            'lifecycle_state': self.lifecycle_state,
            'binding_generation': self.binding_generation,
            'managed_by': self.managed_by,
            'binding_source': self.binding_source.value,
            'daemon_generation': self.daemon_generation,
            'desired_state': self.desired_state,
            'reconcile_state': self.reconcile_state,
            'restart_count': self.restart_count,
            'last_reconcile_at': self.last_reconcile_at,
            'last_failure_reason': self.last_failure_reason,
        }


__all__ = ['AgentRuntime']
