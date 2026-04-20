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
    if runtime is None:
        return registry.upsert(
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
                daemon_generation=generation_getter(),
                desired_state='mounted',
                reconcile_state='starting',
                last_reconcile_at=attempted_at,
            )
        )

    candidate = replace(
        runtime,
        state=AgentState.STARTING,
        health='starting',
        workspace_path=runtime.workspace_path or workspace_path,
        backend_type=runtime.backend_type or spec.runtime_mode.value,
        provider=runtime.provider or spec.provider,
        lifecycle_state='starting',
        daemon_generation=generation_getter(),
        desired_state='mounted',
        reconcile_state='starting',
        last_reconcile_at=attempted_at,
    )
    if candidate == runtime:
        return runtime
    return registry.upsert(candidate)


__all__ = ["build_starting_runtime"]
