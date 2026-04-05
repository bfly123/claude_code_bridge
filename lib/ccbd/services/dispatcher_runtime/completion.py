from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from ccbd.api_models import JobRecord
from completion.models import CompletionDecision, CompletionFamily, CompletionState

if TYPE_CHECKING:
    from completion.tracker import CompletionTrackerService, CompletionTrackerView


def apply_tracker_view(
    current: JobRecord,
    tracked: CompletionTrackerView,
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
    timestamp = _resolve_tracker_timestamp(tracked, clock=clock, updated_at=updated_at)
    snapshot_writer.write_completion(
        job_id=current.job_id,
        agent_name=current.agent_name,
        profile_family=profile_family,
        state=tracked.state,
        decision=tracked.decision,
        updated_at=timestamp,
    )
    return timestamp


def merge_terminal_decision(
    job_id: str,
    decision: CompletionDecision,
    *,
    completion_tracker: CompletionTrackerService | None,
    prior_snapshot,
) -> CompletionDecision:
    tracked = completion_tracker.current(job_id) if completion_tracker is not None else None
    prior_state = prior_snapshot.state if prior_snapshot is not None else None
    tracked_state = tracked.state if tracked is not None else None
    reply = decision.reply
    if not reply and tracked is not None:
        reply = tracked.decision.reply
    if not reply and prior_snapshot is not None:
        reply = prior_snapshot.latest_decision.reply
    return replace(
        decision,
        reply=reply,
        anchor_seen=decision.anchor_seen or (tracked_state.anchor_seen if tracked_state else False) or (prior_state.anchor_seen if prior_state else False),
        reply_started=decision.reply_started or (tracked_state.reply_started if tracked_state else False) or (prior_state.reply_started if prior_state else False),
        reply_stable=decision.reply_stable or (tracked_state.reply_stable if tracked_state else False) or (prior_state.reply_stable if prior_state else False),
        provider_turn_ref=decision.provider_turn_ref or (tracked_state.provider_turn_ref if tracked_state else None) or (prior_state.provider_turn_ref if prior_state else None),
        source_cursor=decision.source_cursor or (tracked_state.latest_cursor if tracked_state else None) or (prior_state.latest_cursor if prior_state else None),
    )


def build_terminal_state(decision: CompletionDecision, prior: CompletionState | None) -> CompletionState:
    return CompletionState(
        anchor_seen=decision.anchor_seen or (prior.anchor_seen if prior else False),
        reply_started=decision.reply_started or (prior.reply_started if prior else False),
        reply_stable=decision.reply_stable or (prior.reply_stable if prior else False),
        tool_active=False,
        subagent_activity_seen=prior.subagent_activity_seen if prior else False,
        last_reply_hash=prior.last_reply_hash if prior else None,
        last_reply_at=decision.finished_at or (prior.last_reply_at if prior else None),
        stable_since=prior.stable_since if prior else None,
        provider_turn_ref=decision.provider_turn_ref or (prior.provider_turn_ref if prior else None),
        latest_cursor=decision.source_cursor or (prior.latest_cursor if prior else None),
        terminal=True,
    )


def _resolve_tracker_timestamp(tracked: CompletionTrackerView, *, clock, updated_at: str | None) -> str:
    if updated_at is not None:
        return updated_at
    if tracked.decision.source_cursor is not None:
        return tracked.decision.source_cursor.updated_at
    return clock()
