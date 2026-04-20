from __future__ import annotations

from dataclasses import replace

from agents.models import AgentState
from ccbd.api_models import TargetKind
from ccbd.services.runtime_recovery_policy import (
    HARD_BLOCKED_RUNTIME_HEALTHS,
    RECOVERABLE_RUNTIME_HEALTHS,
    normalized_runtime_health,
)

from ..models import QueuedTargetSlot
from .support import can_attempt_runtime_recovery

RUNNABLE_AGENT_STATES = frozenset({AgentState.IDLE, AgentState.STARTING, AgentState.DEGRADED})


def _degraded_runtime_action(dispatcher, runtime) -> str:
    health = normalized_runtime_health(runtime)
    if health in HARD_BLOCKED_RUNTIME_HEALTHS:
        return "blocked"
    if health not in RECOVERABLE_RUNTIME_HEALTHS:
        return "keep"
    if not can_attempt_runtime_recovery(dispatcher, runtime):
        return "drop"
    return "refresh"


def _refresh_runtime(dispatcher, agent_name: str):
    try:
        return dispatcher._runtime_service.refresh_provider_binding(agent_name, recover=True)
    except Exception:
        return None


def _refreshed_slot(slot: QueuedTargetSlot, refreshed):
    if refreshed is None or refreshed.state not in RUNNABLE_AGENT_STATES:
        return None
    refreshed_health = normalized_runtime_health(refreshed)
    if refreshed_health in HARD_BLOCKED_RUNTIME_HEALTHS or refreshed_health in RECOVERABLE_RUNTIME_HEALTHS:
        return None
    return replace(slot, runtime=refreshed)


def refresh_slot_runtime_for_start(dispatcher, slot: QueuedTargetSlot) -> QueuedTargetSlot | None:
    runtime = slot.runtime
    if slot.target_kind is not TargetKind.AGENT or runtime is None:
        return slot
    if runtime.state is not AgentState.DEGRADED:
        return slot

    action = _degraded_runtime_action(dispatcher, runtime)
    if action == "blocked" or action == "drop":
        return None
    if action == "keep":
        return slot
    return _refreshed_slot(slot, _refresh_runtime(dispatcher, runtime.agent_name))


def _iter_queued_runtimes(dispatcher):
    for agent_name in dispatcher._config.agents:
        if dispatcher._state.active_job(agent_name) is not None:
            continue
        if dispatcher._state.queue_depth(agent_name) == 0:
            continue
        runtime = dispatcher._registry.get(agent_name)
        if runtime is None or runtime.state not in RUNNABLE_AGENT_STATES:
            continue
        yield agent_name, runtime


def iter_runnable_agent_slots(dispatcher):
    for agent_name, runtime in _iter_queued_runtimes(dispatcher):
        if runtime.state is AgentState.DEGRADED:
            action = _degraded_runtime_action(dispatcher, runtime)
            if action in {"blocked", "drop"}:
                continue
        yield QueuedTargetSlot(
            target_kind=TargetKind.AGENT,
            target_name=agent_name,
            runtime=runtime,
        )


__all__ = ["RUNNABLE_AGENT_STATES", "iter_runnable_agent_slots", "refresh_slot_runtime_for_start"]
