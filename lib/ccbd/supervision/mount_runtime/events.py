from __future__ import annotations

from ..store import SupervisionEvent


def record_mount_started(event_store, *, project_id: str, agent_name: str, attempted_at: str, prior_health: str, runtime) -> None:
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


def record_mount_failed(event_store, *, project_id: str, agent_name: str, attempted_at: str, prior_health: str, runtime, reason: str) -> None:
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


def record_mount_succeeded(event_store, *, project_id: str, agent_name: str, attempted_at: str, prior_health: str, runtime) -> None:
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


__all__ = ['record_mount_failed', 'record_mount_started', 'record_mount_succeeded']
