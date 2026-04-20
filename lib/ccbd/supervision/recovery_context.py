from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RecoveryContext:
    project_id: str
    agent_name: str
    runtime: object
    registry: object
    runtime_service: object
    remount_project_fn: object | None
    clock: Callable[[], str]
    event_store: object
    align_runtime_authority_fn: Callable[[object], object]
    upsert_if_changed_fn: Callable[..., object]
    is_in_backoff_window_fn: Callable[..., bool]
    should_reflow_project_namespace_fn: Callable[..., bool]


def build_recovery_context(
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
) -> RecoveryContext:
    return RecoveryContext(
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


__all__ = [
    'RecoveryContext',
    'build_recovery_context',
]
