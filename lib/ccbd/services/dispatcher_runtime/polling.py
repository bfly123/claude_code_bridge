from __future__ import annotations

from completion.tracker import CompletionTrackerView

from .records import append_event, get_job


def poll_completion_updates(dispatcher) -> tuple:
    if dispatcher._execution_service is None:
        return ()
    completed: list = []
    completed_ids: set[str] = set()
    for update in dispatcher._execution_service.poll():
        current = get_job(dispatcher, update.job_id)
        if current is None or current.status in dispatcher._terminal_event_by_status:
            continue
        if dispatcher._completion_tracker is not None and dispatcher._completion_tracker.current(update.job_id) is None:
            dispatcher._completion_tracker.start(current, started_at=current.updated_at)
        tracked: CompletionTrackerView | None = None
        for item in update.items:
            append_event(dispatcher, current, 'completion_item', item.to_record(), timestamp=item.timestamp)
            dispatcher._execution_service.acknowledge_item(update.job_id, event_seq=item.cursor.event_seq)
            if dispatcher._completion_tracker is not None:
                tracked = dispatcher._completion_tracker.ingest(update.job_id, item)
                dispatcher._apply_tracker_view(current, tracked, updated_at=item.timestamp)
        if tracked is None and dispatcher._completion_tracker is not None:
            tracked = dispatcher._completion_tracker.current(update.job_id)
        decision = update.decision
        if decision is None and tracked is not None and tracked.decision.terminal:
            decision = tracked.decision
        if decision is not None:
            completed.append(dispatcher.complete(update.job_id, decision))
            completed_ids.add(update.job_id)
        else:
            dispatcher._execution_service.acknowledge(update.job_id)
    if dispatcher._completion_tracker is not None:
        for tracked in dispatcher._completion_tracker.tick_all(now=dispatcher._clock()):
            current = get_job(dispatcher, tracked.job_id)
            if (
                current is None
                or current.status in dispatcher._terminal_event_by_status
                or tracked.job_id in completed_ids
            ):
                continue
            dispatcher._apply_tracker_view(current, tracked)
            if tracked.decision.terminal:
                completed.append(dispatcher.complete(tracked.job_id, tracked.decision))
                completed_ids.add(tracked.job_id)
    return tuple(completed)
