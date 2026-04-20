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
        if _skip_update(dispatcher, current):
            continue
        tracked = _ingest_update_items(dispatcher, current, update)
        decision = _resolve_update_decision(dispatcher, update, tracked)
        if decision is not None:
            completed.append(dispatcher.complete(update.job_id, decision))
            completed_ids.add(update.job_id)
        else:
            dispatcher._execution_service.acknowledge(update.job_id)
    _tick_tracker(dispatcher, completed, completed_ids)
    return tuple(completed)


def _skip_update(dispatcher, current) -> bool:
    return current is None or current.status in dispatcher._terminal_event_by_status


def _ingest_update_items(dispatcher, current, update) -> CompletionTrackerView | None:
    tracker = dispatcher._completion_tracker
    if tracker is not None and tracker.current(update.job_id) is None:
        tracker.start(current, started_at=current.updated_at)
    tracked: CompletionTrackerView | None = None
    for item in update.items:
        append_event(dispatcher, current, 'completion_item', item.to_record(), timestamp=item.timestamp)
        dispatcher._execution_service.acknowledge_item(update.job_id, event_seq=item.cursor.event_seq)
        if tracker is not None:
            tracked = tracker.ingest(update.job_id, item)
            dispatcher._apply_tracker_view(current, tracked, updated_at=item.timestamp)
    if tracked is None and tracker is not None:
        return tracker.current(update.job_id)
    return tracked


def _resolve_update_decision(dispatcher, update, tracked):
    decision = update.decision
    if decision is None and tracked is not None and tracked.decision.terminal:
        return tracked.decision
    return decision


def _tick_tracker(dispatcher, completed: list, completed_ids: set[str]) -> None:
    tracker = dispatcher._completion_tracker
    if tracker is None:
        return
    for tracked in tracker.tick_all(now=dispatcher._clock()):
        current = get_job(dispatcher, tracked.job_id)
        if _skip_tracked_completion(dispatcher, current, tracked.job_id, completed_ids):
            continue
        dispatcher._apply_tracker_view(current, tracked)
        if tracked.decision.terminal:
            completed.append(dispatcher.complete(tracked.job_id, tracked.decision))
            completed_ids.add(tracked.job_id)


def _skip_tracked_completion(dispatcher, current, job_id: str, completed_ids: set[str]) -> bool:
    return current is None or current.status in dispatcher._terminal_event_by_status or job_id in completed_ids


__all__ = ['poll_completion_updates']
