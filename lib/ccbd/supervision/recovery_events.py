from __future__ import annotations

from .recovery_context import RecoveryContext
from .store import SupervisionEvent


def append_recovery_event(
    ctx: RecoveryContext,
    *,
    event_kind: str,
    occurred_at: str,
    runtime,
    prior_health: str,
    result_health: str,
    details: dict[str, object] | None = None,
) -> None:
    ctx.event_store.append(
        SupervisionEvent(
            event_kind=event_kind,
            project_id=ctx.project_id,
            agent_name=ctx.agent_name,
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


__all__ = ['append_recovery_event']
