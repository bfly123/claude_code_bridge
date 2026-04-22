from __future__ import annotations

from dataclasses import replace

from agents.models import AgentState


def build_starting_runtime(
    agent_name: str,
    *,
    runtime,
    attempted_at: str,
    layout,
    registry,
    runtime_service,
    generation_getter,
):
    spec = registry.spec_for(agent_name)
    workspace_path = str(layout.workspace_path(agent_name, workspace_root=spec.workspace_root))
    generation = generation_getter()
    if runtime is None:
        return registry.upsert_authority(
            replace(
                runtime_service.attach(
                    agent_name=agent_name,
                    workspace_path=workspace_path,
                    backend_type=spec.runtime_mode.value,
                    health='starting',
                    provider=spec.provider,
                    lifecycle_state='starting',
                    managed_by='ccbd',
                    binding_source='provider-session',
                ),
                state=AgentState.STARTING,
                health='starting',
                lifecycle_state='starting',
                daemon_generation=generation,
                desired_state='mounted',
                reconcile_state='starting',
                last_reconcile_at=attempted_at,
            )
        )

    current = runtime
    if authority_adopt_required(runtime, generation=generation):
        current = runtime_service.adopt_runtime_authority(
            runtime,
            daemon_generation=generation,
        )

    candidate = replace(
        current,
        state=AgentState.STARTING,
        health='starting',
        workspace_path=current.workspace_path or workspace_path,
        backend_type=current.backend_type or spec.runtime_mode.value,
        provider=current.provider or spec.provider,
        lifecycle_state='starting',
        daemon_generation=current.daemon_generation,
        desired_state='mounted',
        reconcile_state='starting',
        last_reconcile_at=attempted_at,
    )
    if candidate == current:
        return current
    return registry.upsert_authority(candidate)


def authority_adopt_required(runtime, *, generation: int | None) -> bool:
    if generation is None:
        return False
    if runtime.state not in {AgentState.IDLE, AgentState.BUSY, AgentState.DEGRADED}:
        return False
    current_generation = getattr(runtime, 'daemon_generation', None)
    try:
        current_generation = int(current_generation) if current_generation is not None else None
    except Exception:
        current_generation = None
    return current_generation != int(generation)


__all__ = ["build_starting_runtime"]
