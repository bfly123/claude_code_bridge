from __future__ import annotations

from agents.models import AgentValidationError

from .helpers import restore_attachment_kwargs, runtime_is_active, touch_active_runtime


def ensure_runtime_ready(
    *,
    layout,
    registry,
    restore_store,
    attach_runtime_fn,
    restore_runtime_fn,
    clock,
    agent_name: str,
):
    spec = registry.spec_for(agent_name)
    runtime = registry.get(spec.name)
    if runtime_is_active(runtime):
        return touch_active_runtime(registry=registry, runtime=runtime, timestamp=clock())

    restore_state = restore_store.load(spec.name)
    if runtime is None and restore_state is None:
        raise AgentValidationError(f'agent {spec.name} has no runtime or restore state; start it first')

    attached = attach_runtime_fn(
        **restore_attachment_kwargs(layout=layout, spec=spec, runtime=runtime),
        health='restored' if restore_state is not None else 'healthy',
    )
    if restore_state is not None:
        restore_runtime_fn(spec.name)
        refreshed = registry.get(spec.name)
        if refreshed is not None:
            return refreshed
    return attached


__all__ = ["ensure_runtime_ready"]
