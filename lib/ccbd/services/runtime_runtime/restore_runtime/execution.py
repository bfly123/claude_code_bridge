from __future__ import annotations

from dataclasses import replace

from agents.models import AgentValidationError, RestoreStatus

from .helpers import restore_attachment_kwargs, runtime_is_active, touch_active_runtime


def restore_runtime(
    *,
    layout,
    registry,
    restore_store,
    attach_runtime_fn,
    clock,
    agent_name: str,
):
    spec = registry.spec_for(agent_name)
    state = restore_store.load(spec.name)
    runtime = registry.get(spec.name)
    if state is None:
        raise AgentValidationError(f'no restore state for agent {spec.name}')
    timestamp = clock()
    if runtime_is_active(runtime):
        touch_active_runtime(registry=registry, runtime=runtime, timestamp=timestamp, health='restored')
    else:
        attach_runtime_fn(
            **restore_attachment_kwargs(layout=layout, spec=spec, runtime=runtime),
            health='restored',
        )
    updated_state = replace(
        state,
        last_restore_status=RestoreStatus.CHECKPOINT if state.last_checkpoint else RestoreStatus.FRESH,
    )
    restore_store.save(spec.name, updated_state)
    return updated_state


__all__ = ["restore_runtime"]
