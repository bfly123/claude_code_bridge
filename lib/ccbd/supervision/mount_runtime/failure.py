from __future__ import annotations

from agents.models import AgentState

from ..store import SupervisionEvent


def persist_mount_failure(
    runtime,
    *,
    project_id: str,
    agent_name: str,
    attempted_at: str,
    prior_health: str,
    next_restart_count: int,
    reason: str,
    event_store,
    upsert_if_changed_fn,
) -> str:
    failed = upsert_if_changed_fn(
        runtime,
        state=AgentState.FAILED,
        health='start-failed',
        lifecycle_state='failed',
        reconcile_state='failed',
        restart_count=next_restart_count,
        last_reconcile_at=attempted_at,
        last_failure_reason=reason,
    )
    event_store.append(
        SupervisionEvent(
            event_kind='mount_failed',
            project_id=project_id,
            agent_name=agent_name,
            occurred_at=attempted_at,
            daemon_generation=failed.daemon_generation,
            desired_state=failed.desired_state,
            reconcile_state=failed.reconcile_state,
            prior_health=prior_health,
            result_health=failed.health,
            runtime_state=failed.state.value,
            runtime_ref=failed.runtime_ref,
            session_ref=failed.session_ref,
            details={'reason': failed.last_failure_reason or reason},
        )
    )
    return failed.health


__all__ = ["persist_mount_failure"]
