from __future__ import annotations

from .events import record_mount_started, record_mount_succeeded
from .transitions import (
    SUCCESS_RUNTIME_HEALTHS,
    in_backoff_window,
    missing_mount_action_health,
    mount_actions_missing,
    mount_or_reflow,
    persist_mount_exception,
    persist_mount_success,
    start_mount_attempt,
)


def ensure_mounted(
    *,
    project_id: str,
    agent_name: str,
    runtime,
    registry,
    runtime_service,
    mount_agent_fn,
    remount_project_fn,
    clock,
    event_store,
    upsert_if_changed_fn,
    build_starting_runtime_fn,
    persist_mount_failure_fn,
    is_in_backoff_window_fn,
    should_reflow_project_mount_fn,
    align_runtime_authority_fn,
    normalized_runtime_health_fn,
) -> str:
    del runtime_service
    if mount_actions_missing(mount_agent_fn=mount_agent_fn, remount_project_fn=remount_project_fn):
        return missing_mount_action_health(runtime)

    attempted_at = clock()
    if in_backoff_window(runtime, attempted_at=attempted_at, is_in_backoff_window_fn=is_in_backoff_window_fn):
        return runtime.health

    starting, prior_health, next_restart_count = start_mount_attempt(
        agent_name=agent_name,
        runtime=runtime,
        attempted_at=attempted_at,
        build_starting_runtime_fn=build_starting_runtime_fn,
    )
    record_mount_started(
        event_store,
        project_id=project_id,
        agent_name=agent_name,
        attempted_at=attempted_at,
        prior_health=prior_health,
        runtime=starting,
    )

    try:
        mount_or_reflow(
            agent_name,
            mount_agent_fn=mount_agent_fn,
            remount_project_fn=remount_project_fn,
            should_reflow_project_mount_fn=should_reflow_project_mount_fn,
        )
    except Exception as exc:
        return persist_mount_exception(
            starting,
            project_id=project_id,
            agent_name=agent_name,
            attempted_at=attempted_at,
            prior_health=prior_health,
            next_restart_count=next_restart_count,
            exc=exc,
            event_store=event_store,
            upsert_if_changed_fn=upsert_if_changed_fn,
        )

    refreshed = registry.get(agent_name)
    if refreshed is None:
        return persist_mount_failure_fn(
            starting,
            agent_name=agent_name,
            attempted_at=attempted_at,
            prior_health=prior_health,
            next_restart_count=next_restart_count,
            reason='runtime-missing-after-mount',
        )

    refreshed = align_runtime_authority_fn(refreshed)
    refreshed_health = normalized_runtime_health_fn(refreshed) or refreshed.health
    if refreshed_health not in SUCCESS_RUNTIME_HEALTHS:
        return persist_mount_failure_fn(
            refreshed,
            agent_name=agent_name,
            attempted_at=attempted_at,
            prior_health=prior_health,
            next_restart_count=next_restart_count,
            reason=refreshed_health or 'mount-produced-unhealthy-runtime',
        )

    mounted = persist_mount_success(
        refreshed,
        attempted_at=attempted_at,
        next_restart_count=next_restart_count,
        upsert_if_changed_fn=upsert_if_changed_fn,
    )
    record_mount_succeeded(
        event_store,
        project_id=project_id,
        agent_name=agent_name,
        attempted_at=attempted_at,
        prior_health=prior_health,
        runtime=mounted,
    )
    return mounted.health


__all__ = ["ensure_mounted"]
