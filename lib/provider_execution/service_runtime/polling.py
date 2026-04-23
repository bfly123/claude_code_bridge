from __future__ import annotations

from .models import ExecutionUpdate
from .persistence import persist_submission
from .reliability import apply_reliability_progress, timeout_poll_result


def poll_updates(service) -> tuple[ExecutionUpdate, ...]:
    updates: list[ExecutionUpdate] = []
    now = service._clock()
    replayed_job_ids = drain_pending_replays(service, updates)

    for job_id, submission in list(service._active.items()):
        if should_skip_active_job(job_id, replayed_job_ids):
            continue
        process_active_job(
            service,
            updates,
            job_id=job_id,
            submission=submission,
            now=now,
        )

    return tuple(updates)


def drain_pending_replays(service, updates: list[ExecutionUpdate]) -> set[str]:
    replayed_job_ids: set[str] = set()
    for job_id, replay in list(service._pending_replays.items()):
        items, decision = replay
        updates.append(ExecutionUpdate(job_id=job_id, items=items, decision=decision))
        replayed_job_ids.add(job_id)
        if should_keep_pending_replay(service, job_id=job_id, decision=decision):
            continue
        service._pending_replays.pop(job_id, None)
    return replayed_job_ids


def should_keep_pending_replay(service, *, job_id: str, decision) -> bool:
    return bool(
        decision is not None
        and decision.terminal
        and job_id not in service._active
    )


def should_skip_active_job(job_id: str, replayed_job_ids: set[str]) -> bool:
    return job_id in replayed_job_ids


def process_active_job(
    service,
    updates: list[ExecutionUpdate],
    *,
    job_id: str,
    submission,
    now: str,
) -> None:
    adapter = service._registry.get(submission.provider)
    if adapter is None:
        service._active.pop(job_id, None)
        return

    result = adapter.poll(submission, now=now)
    if result is None:
        result = timeout_poll_result(
            service,
            job_id=job_id,
            submission=submission,
            adapter=adapter,
            now=now,
        )
        if result is None:
            return
    else:
        result = apply_reliability_progress(
            result,
            previous_submission=submission,
            now=now,
        )

    service._active[job_id] = result.submission
    persist_submission(
        service,
        job_id,
        pending_decision=terminal_pending_decision(result.decision),
        pending_items=result.items,
    )
    if not should_emit_update(result):
        return

    updates.append(
        ExecutionUpdate(
            job_id=job_id,
            items=result.items,
            decision=result.decision,
        )
    )
    if terminal_pending_decision(result.decision) is not None:
        service._active.pop(job_id, None)
        service._runtime_contexts.pop(job_id, None)


def terminal_pending_decision(decision):
    if decision is None or not decision.terminal:
        return None
    return decision


def should_emit_update(result) -> bool:
    return bool(result.items or result.decision is not None)


__all__ = ["poll_updates"]
