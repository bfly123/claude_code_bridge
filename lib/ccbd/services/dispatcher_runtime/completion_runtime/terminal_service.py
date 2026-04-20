from __future__ import annotations

from dataclasses import replace

from completion.models import CompletionDecision, CompletionState


def merge_terminal_decision(job_id: str, decision: CompletionDecision, *, completion_tracker, prior_snapshot) -> CompletionDecision:
    tracked = completion_tracker.current(job_id) if completion_tracker is not None else None
    prior_state = prior_snapshot.state if prior_snapshot is not None else None
    tracked_state = tracked.state if tracked is not None else None
    return replace(
        decision,
        reply=decision.reply or _tracked_reply(tracked) or _prior_reply(prior_snapshot),
        anchor_seen=_flag(decision.anchor_seen, tracked_state, prior_state, 'anchor_seen'),
        reply_started=_flag(decision.reply_started, tracked_state, prior_state, 'reply_started'),
        reply_stable=_flag(decision.reply_stable, tracked_state, prior_state, 'reply_stable'),
        provider_turn_ref=_value(decision.provider_turn_ref, tracked_state, prior_state, 'provider_turn_ref'),
        source_cursor=_value(decision.source_cursor, tracked_state, prior_state, 'latest_cursor'),
    )


def build_terminal_state(decision: CompletionDecision, prior: CompletionState | None) -> CompletionState:
    return CompletionState(
        anchor_seen=decision.anchor_seen or _state_flag(prior, 'anchor_seen'),
        reply_started=decision.reply_started or _state_flag(prior, 'reply_started'),
        reply_stable=decision.reply_stable or _state_flag(prior, 'reply_stable'),
        tool_active=False,
        subagent_activity_seen=_state_flag(prior, 'subagent_activity_seen'),
        last_reply_hash=_state_value(prior, 'last_reply_hash'),
        last_reply_at=decision.finished_at or _state_value(prior, 'last_reply_at'),
        stable_since=_state_value(prior, 'stable_since'),
        provider_turn_ref=decision.provider_turn_ref or _state_value(prior, 'provider_turn_ref'),
        latest_cursor=decision.source_cursor or _state_value(prior, 'latest_cursor'),
        terminal=True,
    )


def _flag(current: bool, tracked_state, prior_state, name: str) -> bool:
    return current or _state_flag(tracked_state, name) or _state_flag(prior_state, name)


def _value(current, tracked_state, prior_state, name: str):
    return current or _state_value(tracked_state, name) or _state_value(prior_state, name)


def _tracked_reply(tracked) -> str | None:
    return tracked.decision.reply if tracked is not None else None


def _prior_reply(prior_snapshot) -> str | None:
    return prior_snapshot.latest_decision.reply if prior_snapshot is not None else None


def _state_flag(state, name: str) -> bool:
    return bool(getattr(state, name, False)) if state is not None else False


def _state_value(state, name: str):
    return getattr(state, name, None) if state is not None else None


__all__ = ['build_terminal_state', 'merge_terminal_decision']
