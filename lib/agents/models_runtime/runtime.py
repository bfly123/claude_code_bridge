from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import AgentState, RestoreMode, RestoreStatus, RuntimeBindingSource, normalize_runtime_binding_source
from .names import SCHEMA_VERSION, AgentValidationError, normalize_agent_name


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
        self.binding_source = normalize_runtime_binding_source(self.binding_source)
        if not self.project_id:
            raise AgentValidationError('project_id cannot be empty')
        if self.queue_depth < 0:
            raise AgentValidationError('queue_depth cannot be negative')
        if self.state in {AgentState.IDLE, AgentState.BUSY, AgentState.DEGRADED} and not self.workspace_path:
            raise AgentValidationError('workspace_path is required for active runtime states')
        if self.binding_generation <= 0:
            raise AgentValidationError('binding_generation must be positive')
        if self.daemon_generation is not None and self.daemon_generation <= 0:
            raise AgentValidationError('daemon_generation must be positive when set')
        if self.restart_count < 0:
            raise AgentValidationError('restart_count cannot be negative')
        if not str(self.managed_by or '').strip():
            raise AgentValidationError('managed_by cannot be empty')
        if not str(self.lifecycle_state or '').strip():
            self.lifecycle_state = self.state.value
        self.desired_state = _normalized_text(self.desired_state) or _default_desired_state(self.state)
        self.reconcile_state = _normalized_text(self.reconcile_state) or _default_reconcile_state(self.state)
        self.last_reconcile_at = _normalized_text(self.last_reconcile_at)
        self.last_failure_reason = _normalized_text(self.last_failure_reason)

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


def _normalized_text(value: str | None) -> str | None:
    text = str(value or '').strip()
    return text or None


def _default_desired_state(state: AgentState) -> str:
    if state is AgentState.STOPPED:
        return 'stopped'
    return 'mounted'


def _default_reconcile_state(state: AgentState) -> str:
    if state is AgentState.DEGRADED:
        return 'degraded'
    if state is AgentState.STOPPED:
        return 'stopped'
    if state is AgentState.FAILED:
        return 'failed'
    return 'steady'


@dataclass
class AgentRestoreState:
    restore_mode: RestoreMode
    last_checkpoint: str | None
    conversation_summary: str
    open_tasks: list[str] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    base_commit: str | None = None
    head_commit: str | None = None
    last_restore_status: RestoreStatus | None = None

    def __post_init__(self) -> None:
        if not self.conversation_summary.strip() and self.last_checkpoint is None:
            raise AgentValidationError(
                'conversation_summary cannot be empty when last_checkpoint is missing'
            )

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'agent_restore_state',
            'restore_mode': self.restore_mode.value,
            'last_checkpoint': self.last_checkpoint,
            'conversation_summary': self.conversation_summary,
            'open_tasks': list(self.open_tasks),
            'files_touched': list(self.files_touched),
            'base_commit': self.base_commit,
            'head_commit': self.head_commit,
            'last_restore_status': self.last_restore_status.value if self.last_restore_status else None,
        }


__all__ = ['AgentRestoreState', 'AgentRuntime']
