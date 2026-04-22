from __future__ import annotations

from dataclasses import replace

from agents.models import AgentState, RuntimeMode
from ccbd.services.runtime_recovery_policy import normalized_runtime_health, should_attempt_background_recovery
from ccbd.system import parse_utc_timestamp
from ccbd.supervision.backoff import backoff_delay_seconds as backoff_delay_seconds_impl
from ccbd.supervision.backoff import is_in_backoff_window as is_in_backoff_window_impl
from ccbd.supervision.backoff import same_socket_path as same_socket_path_impl
from ccbd.supervision.mount import build_starting_runtime as build_starting_runtime_impl

from .loop_context import RuntimeSupervisionContext


def resolved_runtime(ctx: RuntimeSupervisionContext, agent_name: str):
    runtime = ctx.registry.get(agent_name)
    if runtime is None:
        return None
    return align_runtime_authority(ctx, runtime)


def align_runtime_authority(ctx: RuntimeSupervisionContext, runtime):
    next_generation = ctx.generation_getter()
    aligned = runtime
    if authority_adopt_required(runtime, next_generation=next_generation):
        aligned = ctx.runtime_service.adopt_runtime_authority(
            runtime,
            daemon_generation=next_generation,
        )
    daemon_generation = aligned.daemon_generation if next_generation is None else next_generation
    desired_state = 'stopped' if runtime.state is AgentState.STOPPED else 'mounted'
    reconcile_state = resolved_reconcile_state(aligned)
    return upsert_if_changed(
        ctx,
        aligned,
        daemon_generation=daemon_generation,
        desired_state=desired_state,
        reconcile_state=reconcile_state,
    )


def authority_adopt_required(runtime, *, next_generation: int | None) -> bool:
    if next_generation is None:
        return False
    if runtime.state not in {AgentState.IDLE, AgentState.BUSY, AgentState.DEGRADED}:
        return False
    current_generation = getattr(runtime, 'daemon_generation', None)
    try:
        current_generation = int(current_generation) if current_generation is not None else None
    except Exception:
        current_generation = None
    return current_generation != int(next_generation)


def upsert_if_changed(ctx: RuntimeSupervisionContext, runtime, **updates):
    candidate = replace(runtime, **updates)
    if candidate == runtime:
        return runtime
    return ctx.registry.upsert_authority(candidate)


def build_starting_runtime(
    ctx: RuntimeSupervisionContext,
    agent_name: str,
    *,
    runtime,
    attempted_at: str,
):
    return build_starting_runtime_impl(
        agent_name,
        runtime=runtime,
        attempted_at=attempted_at,
        layout=ctx.layout,
        registry=ctx.registry,
        runtime_service=ctx.runtime_service,
        generation_getter=ctx.generation_getter,
    )


def is_in_backoff_window(
    ctx: RuntimeSupervisionContext,
    runtime,
    *,
    now: str,
) -> bool:
    return is_in_backoff_window_impl(
        runtime,
        now=now,
        parse_utc_timestamp_fn=parse_utc_timestamp,
        backoff_delay_seconds_fn=backoff_delay_seconds_impl,
    )


def runtime_requires_mount(runtime) -> bool:
    return runtime.state in {AgentState.STOPPED, AgentState.FAILED}


def runtime_requires_mount_from_foreign_pane(ctx: RuntimeSupervisionContext, runtime) -> bool:
    return runtime_health(runtime) == 'pane-foreign' and not should_reflow_project_namespace(ctx, runtime)


def runtime_requires_recovery(ctx: RuntimeSupervisionContext, runtime) -> bool:
    return should_reflow_project_namespace(ctx, runtime) or should_attempt_background_recovery(runtime)


def runtime_health(runtime) -> str:
    return normalized_runtime_health(runtime)


def should_reflow_project_namespace(ctx: RuntimeSupervisionContext, runtime, *, recovered=None) -> bool:
    if recovered is not None and recovered_replacement_requires_workspace_reflow(ctx, runtime, recovered):
        return True
    if not runtime_in_project_namespace_reflow_health(runtime):
        return False
    if not project_namespace_reflow_safe(ctx, runtime.agent_name):
        return False
    socket_path = str(getattr(runtime, 'tmux_socket_path', None) or '').strip()
    if not socket_path:
        return False
    return same_socket_path_impl(socket_path, str(ctx.layout.ccbd_tmux_socket_path))


def should_reflow_project_mount(ctx: RuntimeSupervisionContext, agent_name: str) -> bool:
    if not bool(getattr(ctx.config, 'cmd_enabled', False)):
        return False
    return project_namespace_reflow_safe(ctx, agent_name)


def project_namespace_reflow_safe(ctx: RuntimeSupervisionContext, agent_name: str) -> bool:
    if ctx.remount_project_fn is None:
        return False
    spec = runtime_mode_spec(ctx, agent_name)
    if spec is None:
        return False
    if getattr(spec, 'runtime_mode', None) is not RuntimeMode.PANE_BACKED:
        return False
    return not other_project_agent_busy(ctx, agent_name)


def resolved_reconcile_state(runtime) -> str | None:
    reconcile_state = runtime.reconcile_state
    if runtime.state is AgentState.STOPPED:
        return 'stopped'
    if runtime.state is AgentState.FAILED:
        return 'failed'
    if runtime.state is AgentState.DEGRADED and reconcile_state == 'steady':
        return 'degraded'
    if runtime.state in {AgentState.STARTING, AgentState.IDLE, AgentState.BUSY}:
        if reconcile_state in {None, '', 'degraded', 'recovering', 'failed', 'stopped'}:
            return 'steady'
    return reconcile_state


def runtime_in_project_namespace_reflow_health(runtime) -> bool:
    return runtime_health(runtime) in {'pane-foreign'}


def recovered_replacement_requires_workspace_reflow(ctx: RuntimeSupervisionContext, runtime, recovered) -> bool:
    if runtime_health(runtime) not in {'pane-dead', 'pane-missing'}:
        return False
    if not project_namespace_reflow_safe(ctx, runtime.agent_name):
        return False
    if not runtime_belongs_to_project_socket(ctx, recovered):
        return False
    return recovered_pane_replaced(runtime, recovered)


def runtime_belongs_to_project_socket(ctx: RuntimeSupervisionContext, runtime) -> bool:
    socket_path = str(getattr(runtime, 'tmux_socket_path', None) or '').strip()
    if not socket_path:
        return False
    return same_socket_path_impl(socket_path, str(ctx.layout.ccbd_tmux_socket_path))


def recovered_pane_replaced(runtime, recovered) -> bool:
    previous_pane_id = runtime_active_pane_id(runtime)
    current_pane_id = runtime_active_pane_id(recovered)
    if previous_pane_id is None or current_pane_id is None:
        return False
    return previous_pane_id != current_pane_id


def runtime_active_pane_id(runtime) -> str | None:
    for field_name in ('active_pane_id', 'pane_id'):
        pane_id = str(getattr(runtime, field_name, None) or '').strip()
        if pane_id.startswith('%'):
            return pane_id
    runtime_ref = str(getattr(runtime, 'runtime_ref', None) or '').strip()
    if runtime_ref.startswith('tmux:%'):
        return runtime_ref[len('tmux:') :]
    return None


def runtime_mode_spec(ctx: RuntimeSupervisionContext, agent_name: str):
    try:
        return ctx.registry.spec_for(agent_name)
    except Exception:
        return None


def other_project_agent_busy(ctx: RuntimeSupervisionContext, agent_name: str) -> bool:
    for other_name in ctx.config.agents:
        other = ctx.registry.get(other_name)
        if other is None or other.agent_name == agent_name:
            continue
        if other.state is AgentState.BUSY:
            return True
    return False


__all__ = [
    'align_runtime_authority',
    'build_starting_runtime',
    'is_in_backoff_window',
    'resolved_runtime',
    'recovered_pane_replaced',
    'runtime_health',
    'runtime_requires_mount',
    'runtime_requires_mount_from_foreign_pane',
    'runtime_requires_recovery',
    'should_reflow_project_mount',
    'should_reflow_project_namespace',
    'upsert_if_changed',
]
