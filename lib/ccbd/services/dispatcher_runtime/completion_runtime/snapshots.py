from __future__ import annotations

from typing import TYPE_CHECKING

from ccbd.api_models import JobRecord
from completion.models import CompletionFamily

if TYPE_CHECKING:
    from completion.tracker import CompletionTrackerView


def apply_tracker_view(
    current: JobRecord,
    tracked: 'CompletionTrackerView',
    *,
    snapshot_writer,
    profile_family: CompletionFamily,
    clock,
    updated_at: str | None = None,
) -> str | None:
    prior_snapshot = snapshot_writer.load(current.job_id)
    if prior_snapshot is not None and prior_snapshot.state.terminal and not tracked.decision.terminal:
        return None
    if prior_snapshot is not None and prior_snapshot.state == tracked.state and prior_snapshot.latest_decision == tracked.decision:
        return None
    timestamp = resolve_tracker_timestamp(tracked, clock=clock, updated_at=updated_at)
    snapshot_writer.write_completion(
        job_id=current.job_id,
        agent_name=current.agent_name,
        profile_family=profile_family,
        state=tracked.state,
        decision=tracked.decision,
        updated_at=timestamp,
    )
    return timestamp


def resolve_tracker_timestamp(tracked: 'CompletionTrackerView', *, clock, updated_at: str | None) -> str:
    if updated_at is not None:
        return updated_at
    if tracked.decision.source_cursor is not None:
        return tracked.decision.source_cursor.updated_at
    return clock()


__all__ = ['apply_tracker_view', 'resolve_tracker_timestamp']
