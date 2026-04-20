from __future__ import annotations

from agents.models import AgentState

ACTIVE_RUNTIME_STATES = frozenset({AgentState.STARTING, AgentState.IDLE, AgentState.BUSY, AgentState.DEGRADED})


def fallback_workspace_path(*, layout, spec, runtime) -> str:
    if runtime is not None and str(runtime.workspace_path or '').strip():
        return str(runtime.workspace_path)
    return str(layout.workspace_path(spec.name))
