from __future__ import annotations

from agents.models import AgentState

from ..store import SupervisionEvent

_SUCCESS_RUNTIME_HEALTHS = frozenset({'healthy', 'restored'})


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
    if _mount_actions_missing(mount_agent_fn=mount_agent_fn, remount_project_fn=remount_project_fn):
        return _missing_mount_action_health(runtime)

    attempted_at = clock()
    if _in_backoff_window(runtime, attempted_at=attempted_at, is_in_backoff_window_fn=is_in_backoff_window_fn):
        return runtime.health

    starting, prior_health, next_restart_count = _start_mount_attempt(
        agent_name=agent_name,
        runtime=runtime,
        attempted_at=attempted_at,
        build_starting_runtime_fn=build_starting_runtime_fn,
    )
    _record_mount_started(
        event_store,
        project_id=project_id,
        agent_name=agent_name,
        attempted_at=attempted_at,
        prior_health=prior_health,
        runtime=starting,
    )

    try:
        _mount_or_reflow(
            agent_name,
            mount_agent_fn=mount_agent_fn,
            remount_project_fn=remount_project_fn,
            should_reflow_project_mount_fn=should_reflow_project_mount_fn,
        )
    except Exception as exc:
        return _persist_mount_exception(
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
    if refreshed_health not in _SUCCESS_RUNTIME_HEALTHS:
        return persist_mount_failure_fn(
            refreshed,
            agent_name=agent_name,
            attempted_at=attempted_at,
            prior_health=prior_health,
            next_restart_count=next_restart_count,
            reason=refreshed_health or 'mount-produced-unhealthy-runtime',
        )

    mounted = _persist_mount_success(
        refreshed,
        attempted_at=attempted_at,
        next_restart_count=next_restart_count,
        upsert_if_changed_fn=upsert_if_changed_fn,
    )
    _record_mount_succeeded(
        event_store,
        project_id=project_id,
        agent_name=agent_name,
        attempted_at=attempted_at,
        prior_health=prior_health,
        runtime=mounted,
    )
    return mounted.health


def _mount_actions_missing(*, mount_agent_fn, remount_project_fn) -> bool:
    return mount_agent_fn is None and remount_project_fn is None


def _missing_mount_action_health(runtime) -> str:
    return 'unmounted' if runtime is None else runtime.health


def _in_backoff_window(runtime, *, attempted_at: str, is_in_backoff_window_fn) -> bool:
    return runtime is not None and is_in_backoff_window_fn(runtime, now=attempted_at)


def _start_mount_attempt(
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


def _persist_mount_exception(
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
    _record_mount_failed(
        event_store,
        project_id=project_id,
        agent_name=agent_name,
        attempted_at=attempted_at,
        prior_health=prior_health,
        runtime=failed,
        reason=failed.last_failure_reason or 'mount-failed',
    )
    return failed.health


def _persist_mount_success(
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


def _mount_or_reflow(agent_name: str, *, mount_agent_fn, remount_project_fn, should_reflow_project_mount_fn) -> None:
    if should_reflow_project_mount_fn(agent_name):
        remount_project_fn(f'mount_recovery:{agent_name}')
        return
    mount_agent_fn(agent_name)


def _record_mount_started(event_store, *, project_id: str, agent_name: str, attempted_at: str, prior_health: str, runtime) -> None:
    event_store.append(
        SupervisionEvent(
            event_kind='mount_started',
            project_id=project_id,
            agent_name=agent_name,
            occurred_at=attempted_at,
            daemon_generation=runtime.daemon_generation,
            desired_state=runtime.desired_state,
            reconcile_state=runtime.reconcile_state,
            prior_health=prior_health,
            result_health=runtime.health,
            runtime_state=runtime.state.value,
            runtime_ref=runtime.runtime_ref,
            session_ref=runtime.session_ref,
        )
    )


def _record_mount_failed(event_store, *, project_id: str, agent_name: str, attempted_at: str, prior_health: str, runtime, reason: str) -> None:
    event_store.append(
        SupervisionEvent(
            event_kind='mount_failed',
            project_id=project_id,
            agent_name=agent_name,
            occurred_at=attempted_at,
            daemon_generation=runtime.daemon_generation,
            desired_state=runtime.desired_state,
            reconcile_state=runtime.reconcile_state,
            prior_health=prior_health,
            result_health=runtime.health,
            runtime_state=runtime.state.value,
            runtime_ref=runtime.runtime_ref,
            session_ref=runtime.session_ref,
            details={'reason': reason},
        )
    )


def _record_mount_succeeded(event_store, *, project_id: str, agent_name: str, attempted_at: str, prior_health: str, runtime) -> None:
    event_store.append(
        SupervisionEvent(
            event_kind='mount_succeeded',
            project_id=project_id,
            agent_name=agent_name,
            occurred_at=attempted_at,
            daemon_generation=runtime.daemon_generation,
            desired_state=runtime.desired_state,
            reconcile_state=runtime.reconcile_state,
            prior_health=prior_health,
            result_health=runtime.health,
            runtime_state=runtime.state.value,
            runtime_ref=runtime.runtime_ref,
            session_ref=runtime.session_ref,
            details={'restart_count': runtime.restart_count},
        )
    )


__all__ = ["ensure_mounted"]
