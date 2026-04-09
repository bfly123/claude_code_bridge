from __future__ import annotations

from functools import partial

from ccbd.services.runtime_recovery_policy import normalized_runtime_health
from ccbd.supervision.mount import ensure_mounted as ensure_mounted_impl
from ccbd.supervision.mount import persist_mount_failure as persist_mount_failure_impl
from ccbd.supervision.recovery import recover_runtime as recover_runtime_impl

from .loop_context import RuntimeSupervisionContext
from .loop_runtime import (
    align_runtime_authority,
    build_starting_runtime,
    is_in_backoff_window,
    should_reflow_project_mount,
    should_reflow_project_namespace,
    upsert_if_changed,
)


def ensure_agent_mounted(ctx: RuntimeSupervisionContext, agent_name: str, *, runtime):
    return ensure_mounted_impl(
        project_id=ctx.project_id,
        agent_name=agent_name,
        runtime=runtime,
        registry=ctx.registry,
        runtime_service=ctx.runtime_service,
        mount_agent_fn=ctx.mount_agent_fn,
        remount_project_fn=ctx.remount_project_fn,
        clock=ctx.clock,
        event_store=ctx.event_store,
        upsert_if_changed_fn=partial(upsert_if_changed, ctx),
        build_starting_runtime_fn=partial(build_starting_runtime, ctx),
        persist_mount_failure_fn=partial(persist_mount_failure, ctx),
        is_in_backoff_window_fn=partial(is_in_backoff_window, ctx),
        should_reflow_project_mount_fn=partial(should_reflow_project_mount, ctx),
        align_runtime_authority_fn=partial(align_runtime_authority, ctx),
        normalized_runtime_health_fn=normalized_runtime_health,
    )


def persist_mount_failure(
    ctx: RuntimeSupervisionContext,
    runtime,
    *,
    agent_name: str,
    attempted_at: str,
    prior_health: str,
    next_restart_count: int,
    reason: str,
) -> str:
    return persist_mount_failure_impl(
        runtime,
        project_id=ctx.project_id,
        agent_name=agent_name,
        attempted_at=attempted_at,
        prior_health=prior_health,
        next_restart_count=next_restart_count,
        reason=reason,
        event_store=ctx.event_store,
        upsert_if_changed_fn=partial(upsert_if_changed, ctx),
    )


def recover_agent_runtime(ctx: RuntimeSupervisionContext, agent_name: str, *, runtime) -> str:
    return recover_runtime_impl(
        project_id=ctx.project_id,
        agent_name=agent_name,
        runtime=runtime,
        registry=ctx.registry,
        runtime_service=ctx.runtime_service,
        remount_project_fn=ctx.remount_project_fn,
        clock=ctx.clock,
        event_store=ctx.event_store,
        align_runtime_authority_fn=partial(align_runtime_authority, ctx),
        upsert_if_changed_fn=partial(upsert_if_changed, ctx),
        is_in_backoff_window_fn=partial(is_in_backoff_window, ctx),
        should_reflow_project_namespace_fn=partial(should_reflow_project_namespace, ctx),
    )


__all__ = [
    'ensure_agent_mounted',
    'recover_agent_runtime',
]
