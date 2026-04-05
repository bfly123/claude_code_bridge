from __future__ import annotations

from dataclasses import dataclass, replace

from agents.models import AgentRuntime, AgentState
from ccbd.api_models import JobRecord, JobStatus, TargetKind
from ccbd.services.runtime_recovery_policy import HARD_BLOCKED_RUNTIME_HEALTHS, RECOVERABLE_RUNTIME_HEALTHS, normalized_runtime_health

from .context import build_job_runtime_context
from .records import append_event, append_job, get_job
from .reply_delivery import claim_reply_delivery_start, claimable_reply_delivery_job_ids
from .runtime_state import sync_runtime

_RUNNABLE_AGENT_STATES = frozenset({AgentState.IDLE, AgentState.STARTING, AgentState.DEGRADED})


def _provider_supports_resume(dispatcher, agent_name: str) -> bool:
    try:
        spec = dispatcher._registry.spec_for(agent_name)
        manifest = dispatcher._provider_catalog.get(spec.provider)
    except Exception:
        return False
    return bool(manifest.supports_resume)


def _can_attempt_runtime_recovery(dispatcher, runtime: AgentRuntime) -> bool:
    if dispatcher._execution_service is None or dispatcher._runtime_service is None:
        return False
    if normalized_runtime_health(runtime) not in RECOVERABLE_RUNTIME_HEALTHS:
        return False
    return _provider_supports_resume(dispatcher, runtime.agent_name)


@dataclass(frozen=True)
class _QueuedTargetSlot:
    target_kind: TargetKind
    target_name: str
    runtime: AgentRuntime | None = None

    @property
    def requires_runtime_sync(self) -> bool:
        return self.target_kind is TargetKind.AGENT


def _write_running_snapshot(dispatcher, running: JobRecord, *, started_at: str) -> None:
    if dispatcher._completion_tracker is not None:
        tracked = dispatcher._completion_tracker.start(running, started_at=started_at)
        dispatcher._snapshot_writer.write_completion(
            job_id=running.job_id,
            agent_name=running.agent_name,
            profile_family=dispatcher._profile_family_for_job(running),
            state=tracked.state,
            decision=tracked.decision,
            updated_at=started_at,
        )
        return
    dispatcher._snapshot_writer.write_pending(
        job_id=running.job_id,
        agent_name=running.agent_name,
        profile_family=dispatcher._profile_family_for_job(running),
    )


def _start_running_job(
    dispatcher,
    current: JobRecord,
    *,
    slot: _QueuedTargetSlot,
    started_at: str | None = None,
) -> JobRecord:
    started_at = started_at or dispatcher._clock()
    running = replace(current, status=JobStatus.RUNNING, updated_at=started_at)
    append_job(dispatcher, running)
    append_event(dispatcher, running, 'job_started', {'status': JobStatus.RUNNING.value}, timestamp=started_at)
    _write_running_snapshot(dispatcher, running, started_at=started_at)
    if dispatcher._execution_service is not None:
        dispatcher._execution_service.start(
            running,
            runtime_context=build_job_runtime_context(running, slot.runtime),
        )
    dispatcher._state.mark_active_for(running.target_kind, running.target_name, running.job_id)
    if slot.requires_runtime_sync:
        sync_runtime(dispatcher, running.agent_name, state=AgentState.BUSY)
    if dispatcher._message_bureau is not None:
        dispatcher._message_bureau.mark_attempt_started(running, started_at=started_at)
    return running


def _refresh_slot_runtime_for_start(dispatcher, slot: _QueuedTargetSlot) -> _QueuedTargetSlot | None:
    runtime = slot.runtime
    if slot.target_kind is not TargetKind.AGENT or runtime is None:
        return slot
    if runtime.state is not AgentState.DEGRADED:
        return slot

    health = normalized_runtime_health(runtime)
    if health in HARD_BLOCKED_RUNTIME_HEALTHS:
        return None
    if health not in RECOVERABLE_RUNTIME_HEALTHS:
        return slot
    if not _can_attempt_runtime_recovery(dispatcher, runtime):
        return None

    try:
        refreshed = dispatcher._runtime_service.refresh_provider_binding(runtime.agent_name, recover=True)
    except Exception:
        refreshed = None
    if refreshed is None or refreshed.state not in _RUNNABLE_AGENT_STATES:
        return None

    refreshed_health = normalized_runtime_health(refreshed)
    if refreshed_health in HARD_BLOCKED_RUNTIME_HEALTHS or refreshed_health in RECOVERABLE_RUNTIME_HEALTHS:
        return None
    return replace(slot, runtime=refreshed)


def _start_next_queued_job(dispatcher, slot: _QueuedTargetSlot) -> JobRecord | None:
    slot = _refresh_slot_runtime_for_start(dispatcher, slot)
    if slot is None:
        return None
    job_id = None
    if dispatcher._message_bureau is not None and slot.target_kind is TargetKind.AGENT:
        queued_ids = set(dispatcher._state.queued_items_for(slot.target_kind, slot.target_name))
        for candidate in claimable_reply_delivery_job_ids(dispatcher, slot.target_name):
            if candidate not in queued_ids:
                continue
            current = get_job(dispatcher, candidate)
            if current is None:
                dispatcher._state.remove_queued_for(slot.target_kind, slot.target_name, candidate)
                continue
            started_at = dispatcher._clock()
            if not claim_reply_delivery_start(dispatcher, current, started_at=started_at):
                continue
            dispatcher._state.remove_queued_for(slot.target_kind, slot.target_name, candidate)
            return _start_running_job(dispatcher, current, slot=slot, started_at=started_at)
        for candidate in dispatcher._message_bureau.claimable_request_job_ids(slot.target_name):
            if candidate not in queued_ids:
                continue
            dispatcher._state.remove_queued_for(slot.target_kind, slot.target_name, candidate)
            job_id = candidate
            break
        if job_id is None:
            return None
    else:
        job_id = dispatcher._state.pop_next_for(slot.target_kind, slot.target_name)
        if job_id is None:
            return None
    current = get_job(dispatcher, job_id)
    if current is None:
        return None
    return _start_running_job(dispatcher, current, slot=slot)


def _iter_runnable_agent_slots(dispatcher):
    for agent_name in dispatcher._config.agents:
        if dispatcher._state.active_job(agent_name) is not None:
            continue
        if dispatcher._state.queue_depth(agent_name) == 0:
            continue
        runtime = dispatcher._registry.get(agent_name)
        if runtime is None or runtime.state not in _RUNNABLE_AGENT_STATES:
            continue
        if runtime.state is AgentState.DEGRADED:
            health = normalized_runtime_health(runtime)
            if health in HARD_BLOCKED_RUNTIME_HEALTHS:
                continue
            if health in RECOVERABLE_RUNTIME_HEALTHS and not _can_attempt_runtime_recovery(dispatcher, runtime):
                continue
        yield _QueuedTargetSlot(
            target_kind=TargetKind.AGENT,
            target_name=agent_name,
            runtime=runtime,
        )


def _iter_runnable_slots(dispatcher):
    yield from _iter_runnable_agent_slots(dispatcher)


def tick_jobs(dispatcher) -> tuple[JobRecord, ...]:
    started: list[JobRecord] = []
    for slot in _iter_runnable_slots(dispatcher):
        running = _start_next_queued_job(dispatcher, slot)
        if running is not None:
            started.append(running)
    return tuple(started)


__all__ = ['tick_jobs']
