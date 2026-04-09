from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .store import SupervisionEventStore


@dataclass(frozen=True)
class RuntimeSupervisionContext:
    project_id: str
    layout: object
    config: object
    registry: object
    runtime_service: object
    mount_agent_fn: object | None
    remount_project_fn: object | None
    clock: Callable[[], str]
    generation_getter: Callable[[], object | None]
    event_store: SupervisionEventStore


def build_runtime_supervision_context(
    *,
    project_id: str,
    layout,
    config,
    registry,
    runtime_service,
    mount_agent_fn=None,
    remount_project_fn=None,
    clock,
    generation_getter=None,
    event_store: SupervisionEventStore | None = None,
) -> RuntimeSupervisionContext:
    return RuntimeSupervisionContext(
        project_id=project_id,
        layout=layout,
        config=config,
        registry=registry,
        runtime_service=runtime_service,
        mount_agent_fn=mount_agent_fn,
        remount_project_fn=remount_project_fn,
        clock=clock,
        generation_getter=generation_getter or (lambda: None),
        event_store=event_store or SupervisionEventStore(layout),
    )


__all__ = [
    'RuntimeSupervisionContext',
    'build_runtime_supervision_context',
]
