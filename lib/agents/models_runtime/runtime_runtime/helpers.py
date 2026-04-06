from __future__ import annotations

from agents.models_runtime.enums import AgentState, normalize_runtime_binding_source
from agents.models_runtime.names import AgentValidationError


def normalized_text(value: str | None) -> str | None:
    text = str(value or '').strip()
    return text or None


def default_desired_state(state: AgentState) -> str:
    if state is AgentState.STOPPED:
        return 'stopped'
    return 'mounted'


def default_reconcile_state(state: AgentState) -> str:
    if state is AgentState.DEGRADED:
        return 'degraded'
    if state is AgentState.STOPPED:
        return 'stopped'
    if state is AgentState.FAILED:
        return 'failed'
    return 'steady'


def normalize_runtime_defaults(runtime) -> None:
    runtime.binding_source = normalize_runtime_binding_source(runtime.binding_source)
    if not str(runtime.lifecycle_state or '').strip():
        runtime.lifecycle_state = runtime.state.value
    runtime.desired_state = normalized_text(runtime.desired_state) or default_desired_state(runtime.state)
    runtime.reconcile_state = normalized_text(runtime.reconcile_state) or default_reconcile_state(runtime.state)
    runtime.last_reconcile_at = normalized_text(runtime.last_reconcile_at)
    runtime.last_failure_reason = normalized_text(runtime.last_failure_reason)


def validate_runtime_fields(runtime) -> None:
    if not runtime.project_id:
        raise AgentValidationError('project_id cannot be empty')
    if runtime.queue_depth < 0:
        raise AgentValidationError('queue_depth cannot be negative')
    if runtime.state in {AgentState.IDLE, AgentState.BUSY, AgentState.DEGRADED} and not runtime.workspace_path:
        raise AgentValidationError('workspace_path is required for active runtime states')
    if runtime.binding_generation <= 0:
        raise AgentValidationError('binding_generation must be positive')
    if runtime.daemon_generation is not None and runtime.daemon_generation <= 0:
        raise AgentValidationError('daemon_generation must be positive when set')
    if runtime.restart_count < 0:
        raise AgentValidationError('restart_count cannot be negative')
    if not str(runtime.managed_by or '').strip():
        raise AgentValidationError('managed_by cannot be empty')


def validate_restore_state(state) -> None:
    if not state.conversation_summary.strip() and state.last_checkpoint is None:
        raise AgentValidationError('conversation_summary cannot be empty when last_checkpoint is missing')


__all__ = [
    'default_desired_state',
    'default_reconcile_state',
    'normalize_runtime_defaults',
    'normalized_text',
    'validate_restore_state',
    'validate_runtime_fields',
]
