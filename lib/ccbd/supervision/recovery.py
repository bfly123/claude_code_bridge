from __future__ import annotations

from ccbd.services.runtime_recovery_policy import normalized_runtime_health

from .recovery_context import build_recovery_context
from .recovery_transitions import (
    SUCCESS_RUNTIME_HEALTHS,
    attempt_recovery_action,
    mark_recovery_failed,
    mark_recovery_missing,
    mark_recovery_succeeded,
    start_recovery,
)


def recover_runtime(
    *,
    project_id: str,
    agent_name: str,
    runtime,
    registry,
    runtime_service,
    remount_project_fn,
    clock,
    event_store,
    align_runtime_authority_fn,
    upsert_if_changed_fn,
    is_in_backoff_window_fn,
    should_reflow_project_namespace_fn,
) -> str:
    ctx = build_recovery_context(
        project_id=project_id,
        agent_name=agent_name,
        runtime=runtime,
        registry=registry,
        runtime_service=runtime_service,
        remount_project_fn=remount_project_fn,
        clock=clock,
        event_store=event_store,
        align_runtime_authority_fn=align_runtime_authority_fn,
        upsert_if_changed_fn=upsert_if_changed_fn,
        is_in_backoff_window_fn=is_in_backoff_window_fn,
        should_reflow_project_namespace_fn=should_reflow_project_namespace_fn,
    )
    attempted_at = ctx.clock()
    if ctx.is_in_backoff_window_fn(ctx.runtime, now=attempted_at):
        return ctx.runtime.health
    prior_health = normalized_runtime_health(ctx.runtime) or ctx.runtime.health
    recovering = start_recovery(
        ctx,
        attempted_at=attempted_at,
        prior_health=prior_health,
    )
    restart_count = recovering.restart_count + 1

    try:
        refreshed, failure_reason = attempt_recovery_action(ctx, recovering=recovering)
    except Exception as exc:
        refreshed = ctx.registry.get(ctx.agent_name) or recovering
        failure_reason = f'{type(exc).__name__}: {exc}'

    if refreshed is None:
        return mark_recovery_missing(
            ctx,
            recovering=recovering,
            attempted_at=attempted_at,
            restart_count=restart_count,
            prior_health=prior_health,
        )

    refreshed = ctx.align_runtime_authority_fn(refreshed)
    next_health = normalized_runtime_health(refreshed) or refreshed.health
    if next_health in SUCCESS_RUNTIME_HEALTHS:
        return mark_recovery_succeeded(
            ctx,
            refreshed=refreshed,
            attempted_at=attempted_at,
            restart_count=restart_count,
            prior_health=prior_health,
            next_health=next_health,
        )

    return mark_recovery_failed(
        ctx,
        refreshed=refreshed,
        attempted_at=attempted_at,
        restart_count=restart_count,
        prior_health=prior_health,
        next_health=next_health,
        failure_reason=failure_reason,
    )
