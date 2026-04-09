from __future__ import annotations

from agents.models import AgentState

from .events import record_mount_failed

SUCCESS_RUNTIME_HEALTHS = frozenset({'healthy', 'restored'})


def mount_actions_missing(*, mount_agent_fn, remount_project_fn) -> bool:
    return mount_agent_fn is None and remount_project_fn is None


def missing_mount_action_health(runtime) -> str:
    return 'unmounted' if runtime is None else runtime.health


def in_backoff_window(runtime, *, attempted_at: str, is_in_backoff_window_fn) -> bool:
    return runtime is not None and is_in_backoff_window_fn(runtime, now=attempted_at)


def start_mount_attempt(
    *,
    agent_name: str,
    runtime,
    attempted_at: str,
    build_starting_runtime_fn,
):
    starting = build_starting_runtime_fn(agent_name, runtime=runtime, attempted_at=attempted_at)
    prior_health = runtime.health if runtime is not None else 'unmounted'
    next_restart_count = starting.restart_count + 1
    return starting, prior_health, next_restart_count


def persist_mount_exception(
    starting,
    *,
    project_id: str,
    agent_name: str,
    attempted_at: str,
    prior_health: str,
    next_restart_count: int,
    exc: Exception,
    event_store,
    upsert_if_changed_fn,
) -> str:
    failed = upsert_if_changed_fn(
        starting,
        state=AgentState.FAILED,
        health='start-failed',
        lifecycle_state='failed',
        reconcile_state='failed',
        restart_count=next_restart_count,
        last_reconcile_at=attempted_at,
        last_failure_reason=f'{type(exc).__name__}: {exc}',
    )
    record_mount_failed(
        event_store,
        project_id=project_id,
        agent_name=agent_name,
        attempted_at=attempted_at,
        prior_health=prior_health,
        runtime=failed,
        reason=failed.last_failure_reason or 'mount-failed',
    )
    return failed.health


def persist_mount_success(
    refreshed,
    *,
    attempted_at: str,
    next_restart_count: int,
    upsert_if_changed_fn,
):
    return upsert_if_changed_fn(
        refreshed,
        state=AgentState.IDLE if refreshed.state is AgentState.STARTING else refreshed.state,
        reconcile_state='steady',
        restart_count=next_restart_count,
        last_reconcile_at=attempted_at,
        last_failure_reason=None,
        lifecycle_state='idle' if refreshed.state is AgentState.STARTING else refreshed.lifecycle_state,
    )


def mount_or_reflow(agent_name: str, *, mount_agent_fn, remount_project_fn, should_reflow_project_mount_fn) -> None:
    if should_reflow_project_mount_fn(agent_name):
        remount_project_fn(f'mount_recovery:{agent_name}')
        return
    mount_agent_fn(agent_name)


__all__ = [
    'SUCCESS_RUNTIME_HEALTHS',
    'in_backoff_window',
    'missing_mount_action_health',
    'mount_actions_missing',
    'mount_or_reflow',
    'persist_mount_exception',
    'persist_mount_success',
    'start_mount_attempt',
]
