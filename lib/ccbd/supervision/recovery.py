from __future__ import annotations

from agents.models import AgentState
from ccbd.services.runtime_recovery_policy import normalized_runtime_health

from .store import SupervisionEvent

_SUCCESS_RUNTIME_HEALTHS = frozenset({'healthy', 'restored'})


def _append_recovery_event(
    event_store,
    *,
    event_kind: str,
    project_id: str,
    agent_name: str,
    occurred_at: str,
    runtime,
    prior_health: str,
    result_health: str,
    details: dict[str, object] | None = None,
) -> None:
    event_store.append(
        SupervisionEvent(
            event_kind=event_kind,
            project_id=project_id,
            agent_name=agent_name,
            occurred_at=occurred_at,
            daemon_generation=runtime.daemon_generation,
            desired_state=runtime.desired_state,
            reconcile_state=runtime.reconcile_state,
            prior_health=prior_health,
            result_health=result_health,
            runtime_state=runtime.state.value,
            runtime_ref=runtime.runtime_ref,
            session_ref=runtime.session_ref,
            details=details or {},
        )
    )


def _start_recovery(
    *,
    runtime,
    attempted_at: str,
    prior_health: str,
    upsert_if_changed_fn,
    event_store,
    project_id: str,
    agent_name: str,
):
    recovering = upsert_if_changed_fn(
        runtime,
        reconcile_state='recovering',
        last_reconcile_at=attempted_at,
        lifecycle_state='recovering',
    )
    _append_recovery_event(
        event_store,
        event_kind='recover_started',
        project_id=project_id,
        agent_name=agent_name,
        occurred_at=attempted_at,
        runtime=recovering,
        prior_health=prior_health,
        result_health=prior_health,
    )
    return recovering


def _attempt_recovery_action(
    *,
    recovering,
    agent_name: str,
    registry,
    runtime_service,
    remount_project_fn,
    should_reflow_project_namespace_fn,
):
    if should_reflow_project_namespace_fn(recovering):
        remount_project_fn(f'pane_recovery:{agent_name}')
        return registry.get(agent_name), None
    return runtime_service.refresh_provider_binding(agent_name, recover=True), None


def _mark_recovery_missing(
    *,
    recovering,
    attempted_at: str,
    restart_count: int,
    prior_health: str,
    upsert_if_changed_fn,
    event_store,
    project_id: str,
    agent_name: str,
) -> str:
    failed = upsert_if_changed_fn(
        recovering,
        reconcile_state='degraded',
        restart_count=restart_count,
        last_reconcile_at=attempted_at,
        last_failure_reason='runtime-missing-after-recover',
        lifecycle_state='degraded',
    )
    _append_recovery_event(
        event_store,
        event_kind='recover_failed',
        project_id=project_id,
        agent_name=agent_name,
        occurred_at=attempted_at,
        runtime=failed,
        prior_health=prior_health,
        result_health='unmounted',
        details={'reason': 'runtime-missing-after-recover'},
    )
    return 'unmounted'


def _mark_recovery_succeeded(
    *,
    refreshed,
    attempted_at: str,
    restart_count: int,
    prior_health: str,
    next_health: str,
    upsert_if_changed_fn,
    event_store,
    project_id: str,
    agent_name: str,
) -> str:
    stabilized = upsert_if_changed_fn(
        refreshed,
        reconcile_state='steady',
        restart_count=restart_count,
        last_reconcile_at=attempted_at,
        last_failure_reason=None,
        lifecycle_state=refreshed.state.value,
    )
    _append_recovery_event(
        event_store,
        event_kind='recover_succeeded',
        project_id=project_id,
        agent_name=agent_name,
        occurred_at=attempted_at,
        runtime=stabilized,
        prior_health=prior_health,
        result_health=next_health,
        details={'restart_count': stabilized.restart_count},
    )
    return stabilized.health


def _mark_recovery_failed(
    *,
    refreshed,
    attempted_at: str,
    restart_count: int,
    prior_health: str,
    next_health: str,
    failure_reason: str | None,
    upsert_if_changed_fn,
    event_store,
    project_id: str,
    agent_name: str,
) -> str:
    failure_runtime = upsert_if_changed_fn(
        refreshed,
        reconcile_state='degraded',
        restart_count=restart_count,
        last_reconcile_at=attempted_at,
        last_failure_reason=failure_reason or next_health or prior_health or 'recover-failed',
        lifecycle_state='degraded' if refreshed.state is AgentState.DEGRADED else refreshed.lifecycle_state,
    )
    _append_recovery_event(
        event_store,
        event_kind='recover_failed',
        project_id=project_id,
        agent_name=agent_name,
        occurred_at=attempted_at,
        runtime=failure_runtime,
        prior_health=prior_health,
        result_health=next_health,
        details={'reason': failure_runtime.last_failure_reason or 'recover-failed'},
    )
    return failure_runtime.health


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
    attempted_at = clock()
    if is_in_backoff_window_fn(runtime, now=attempted_at):
        return runtime.health
    prior_health = normalized_runtime_health(runtime) or runtime.health
    recovering = _start_recovery(
        runtime=runtime,
        attempted_at=attempted_at,
        prior_health=prior_health,
        upsert_if_changed_fn=upsert_if_changed_fn,
        event_store=event_store,
        project_id=project_id,
        agent_name=agent_name,
    )
    restart_count = recovering.restart_count + 1

    try:
        refreshed, failure_reason = _attempt_recovery_action(
            recovering=recovering,
            agent_name=agent_name,
            registry=registry,
            runtime_service=runtime_service,
            remount_project_fn=remount_project_fn,
            should_reflow_project_namespace_fn=should_reflow_project_namespace_fn,
        )
    except Exception as exc:
        refreshed = registry.get(agent_name) or recovering
        failure_reason = f'{type(exc).__name__}: {exc}'

    if refreshed is None:
        return _mark_recovery_missing(
            recovering=recovering,
            attempted_at=attempted_at,
            restart_count=restart_count,
            prior_health=prior_health,
            upsert_if_changed_fn=upsert_if_changed_fn,
            event_store=event_store,
            project_id=project_id,
            agent_name=agent_name,
        )

    refreshed = align_runtime_authority_fn(refreshed)
    next_health = normalized_runtime_health(refreshed) or refreshed.health
    if next_health in _SUCCESS_RUNTIME_HEALTHS:
        return _mark_recovery_succeeded(
            refreshed=refreshed,
            attempted_at=attempted_at,
            restart_count=restart_count,
            prior_health=prior_health,
            next_health=next_health,
            upsert_if_changed_fn=upsert_if_changed_fn,
            event_store=event_store,
            project_id=project_id,
            agent_name=agent_name,
        )

    return _mark_recovery_failed(
        refreshed=refreshed,
        attempted_at=attempted_at,
        restart_count=restart_count,
        prior_health=prior_health,
        next_health=next_health,
        failure_reason=failure_reason,
        upsert_if_changed_fn=upsert_if_changed_fn,
        event_store=event_store,
        project_id=project_id,
        agent_name=agent_name,
    )
