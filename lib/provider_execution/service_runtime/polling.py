from __future__ import annotations

from .models import ExecutionUpdate
from .persistence import persist_submission


def poll_updates(service) -> tuple[ExecutionUpdate, ...]:
    updates: list[ExecutionUpdate] = []
    now = service._clock()
    replayed_job_ids: set[str] = set()

    for job_id, replay in list(service._pending_replays.items()):
        items, decision = replay
        updates.append(ExecutionUpdate(job_id=job_id, items=items, decision=decision))
        replayed_job_ids.add(job_id)
        if decision is not None and decision.terminal and job_id not in service._active:
            continue
        service._pending_replays.pop(job_id, None)

    for job_id, submission in list(service._active.items()):
        if job_id in replayed_job_ids:
            continue
        adapter = service._registry.get(submission.provider)
        if adapter is None:
            service._active.pop(job_id, None)
            continue
        result = adapter.poll(submission, now=now)
        if result is None:
            continue
        service._active[job_id] = result.submission
        persist_submission(
            service,
            job_id,
            pending_decision=result.decision if result.decision and result.decision.terminal else None,
            pending_items=result.items,
        )
        if not result.items and result.decision is None:
            continue
        updates.append(ExecutionUpdate(job_id=job_id, items=result.items, decision=result.decision))
        if result.decision is not None and result.decision.terminal:
            service._active.pop(job_id, None)
            service._runtime_contexts.pop(job_id, None)

    return tuple(updates)


__all__ = ["poll_updates"]
