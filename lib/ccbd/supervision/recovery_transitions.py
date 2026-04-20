from __future__ import annotations

from agents.models import AgentState

from .recovery_context import RecoveryContext
from .recovery_events import append_recovery_event

SUCCESS_RUNTIME_HEALTHS = frozenset({'healthy', 'restored'})


def start_recovery(
    ctx: RecoveryContext,
    *,
    attempted_at: str,
    prior_health: str,
):
    recovering = ctx.upsert_if_changed_fn(
        ctx.runtime,
        reconcile_state='recovering',
        last_reconcile_at=attempted_at,
        lifecycle_state='recovering',
    )
    append_recovery_event(
        ctx,
        event_kind='recover_started',
        occurred_at=attempted_at,
        runtime=recovering,
        prior_health=prior_health,
        result_health=prior_health,
    )
    return recovering


def attempt_recovery_action(ctx: RecoveryContext, *, recovering):
    if ctx.should_reflow_project_namespace_fn(recovering):
        ctx.remount_project_fn(f'pane_recovery:{ctx.agent_name}')
        return ctx.registry.get(ctx.agent_name), None
    refreshed = ctx.runtime_service.refresh_provider_binding(ctx.agent_name, recover=True)
    if refreshed is None:
        return None, None
    if ctx.should_reflow_project_namespace_fn(recovering, recovered=refreshed):
        ctx.remount_project_fn(f'pane_recovery:{ctx.agent_name}')
        return ctx.registry.get(ctx.agent_name), None
    return refreshed, None


def mark_recovery_missing(
    ctx: RecoveryContext,
    *,
    recovering,
    attempted_at: str,
    restart_count: int,
    prior_health: str,
) -> str:
    failed = ctx.upsert_if_changed_fn(
        recovering,
        reconcile_state='degraded',
        restart_count=restart_count,
        last_reconcile_at=attempted_at,
        last_failure_reason='runtime-missing-after-recover',
        lifecycle_state='degraded',
    )
    append_recovery_event(
        ctx,
        event_kind='recover_failed',
        occurred_at=attempted_at,
        runtime=failed,
        prior_health=prior_health,
        result_health='unmounted',
        details={'reason': 'runtime-missing-after-recover'},
    )
    return 'unmounted'


def mark_recovery_succeeded(
    ctx: RecoveryContext,
    *,
    refreshed,
    attempted_at: str,
    restart_count: int,
    prior_health: str,
    next_health: str,
) -> str:
    stabilized = ctx.upsert_if_changed_fn(
        refreshed,
        reconcile_state='steady',
        restart_count=restart_count,
        last_reconcile_at=attempted_at,
        last_failure_reason=None,
        lifecycle_state=refreshed.state.value,
    )
    append_recovery_event(
        ctx,
        event_kind='recover_succeeded',
        occurred_at=attempted_at,
        runtime=stabilized,
        prior_health=prior_health,
        result_health=next_health,
        details={'restart_count': stabilized.restart_count},
    )
    return stabilized.health


def mark_recovery_failed(
    ctx: RecoveryContext,
    *,
    refreshed,
    attempted_at: str,
    restart_count: int,
    prior_health: str,
    next_health: str,
    failure_reason: str | None,
) -> str:
    failure_runtime = ctx.upsert_if_changed_fn(
        refreshed,
        reconcile_state='degraded',
        restart_count=restart_count,
        last_reconcile_at=attempted_at,
        last_failure_reason=failure_reason or next_health or prior_health or 'recover-failed',
        lifecycle_state='degraded' if refreshed.state is AgentState.DEGRADED else refreshed.lifecycle_state,
    )
    append_recovery_event(
        ctx,
        event_kind='recover_failed',
        occurred_at=attempted_at,
        runtime=failure_runtime,
        prior_health=prior_health,
        result_health=next_health,
        details={'reason': failure_runtime.last_failure_reason or 'recover-failed'},
    )
    return failure_runtime.health


__all__ = [
    'SUCCESS_RUNTIME_HEALTHS',
    'attempt_recovery_action',
    'mark_recovery_failed',
    'mark_recovery_missing',
    'mark_recovery_succeeded',
    'start_recovery',
]
