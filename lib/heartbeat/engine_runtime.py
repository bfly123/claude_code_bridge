from __future__ import annotations

from dataclasses import replace

from completion.models import seconds_between

from .models import HeartbeatAction, HeartbeatDecision, HeartbeatPolicy, HeartbeatState


def evaluate_heartbeat(
    *,
    policy: HeartbeatPolicy,
    subject_kind: str,
    subject_id: str,
    owner: str,
    observed_last_progress_at: str,
    now: str,
    state: HeartbeatState | None = None,
) -> tuple[HeartbeatState, HeartbeatDecision]:
    progress_at = _progress_timestamp(observed_last_progress_at, now=now)
    current = _current_state(
        state,
        subject_kind=subject_kind,
        subject_id=subject_id,
        owner=owner,
        progress_at=progress_at,
        now=now,
    )
    base = _state_with_subject(current, subject_kind=subject_kind, subject_id=subject_id, owner=owner)

    if _progress_advanced(progress_at, current.last_progress_at) and _heartbeat_active(current):
        next_state = _reset_state(base, progress_at=progress_at, now=now)
        return next_state, _decision(HeartbeatAction.RESET, next_state, silence_seconds=0.0)

    base = replace(base, last_progress_at=progress_at)
    silence_seconds = _silence_seconds(progress_at, now=now)
    if silence_seconds < float(policy.silence_start_after_s):
        return base, _decision(HeartbeatAction.IDLE, base, silence_seconds=silence_seconds)

    if _should_enter_heartbeat(base):
        next_state = _enter_state(base, now=now)
        return next_state, _decision(HeartbeatAction.ENTER, next_state, silence_seconds=silence_seconds)

    if _notice_limit_reached(base, policy=policy):
        return base, _decision(HeartbeatAction.IDLE, base, silence_seconds=silence_seconds)

    if _repeat_interval_not_elapsed(base, policy=policy, now=now):
        return base, _decision(HeartbeatAction.IDLE, base, silence_seconds=silence_seconds)

    next_state = _repeat_state(base, now=now)
    return next_state, _decision(HeartbeatAction.REPEAT, next_state, silence_seconds=silence_seconds)


def _progress_timestamp(observed_last_progress_at: str, *, now: str) -> str:
    progress_at = str(observed_last_progress_at or "").strip() or str(now or "").strip()
    if not progress_at:
        raise ValueError("observed_last_progress_at cannot be empty")
    return progress_at


def _current_state(
    state: HeartbeatState | None,
    *,
    subject_kind: str,
    subject_id: str,
    owner: str,
    progress_at: str,
    now: str,
) -> HeartbeatState:
    if state is not None:
        return state
    return HeartbeatState(
        subject_kind=subject_kind,
        subject_id=subject_id,
        owner=owner,
        last_progress_at=progress_at,
        last_notice_at=None,
        heartbeat_started_at=None,
        notice_count=0,
        updated_at=now,
    )


def _state_with_subject(current: HeartbeatState, *, subject_kind: str, subject_id: str, owner: str) -> HeartbeatState:
    return replace(
        current,
        subject_kind=subject_kind,
        subject_id=subject_id,
        owner=owner,
    )


def _heartbeat_active(state: HeartbeatState) -> bool:
    return state.notice_count > 0 or state.last_notice_at is not None


def _reset_state(base: HeartbeatState, *, progress_at: str, now: str) -> HeartbeatState:
    return replace(
        base,
        last_progress_at=progress_at,
        last_notice_at=None,
        heartbeat_started_at=None,
        notice_count=0,
        updated_at=now,
    )


def _enter_state(base: HeartbeatState, *, now: str) -> HeartbeatState:
    return replace(
        base,
        last_notice_at=now,
        heartbeat_started_at=base.heartbeat_started_at or now,
        notice_count=1,
        updated_at=now,
    )


def _repeat_state(base: HeartbeatState, *, now: str) -> HeartbeatState:
    return replace(
        base,
        last_notice_at=now,
        heartbeat_started_at=base.heartbeat_started_at or now,
        notice_count=base.notice_count + 1,
        updated_at=now,
    )


def _silence_seconds(progress_at: str, *, now: str) -> float:
    try:
        return max(0.0, seconds_between(progress_at, now))
    except Exception:
        return 0.0


def _should_enter_heartbeat(state: HeartbeatState) -> bool:
    return state.last_notice_at is None or state.notice_count <= 0


def _notice_limit_reached(state: HeartbeatState, *, policy: HeartbeatPolicy) -> bool:
    if policy.max_notice_count is None:
        return False
    return state.notice_count >= int(policy.max_notice_count)


def _repeat_interval_not_elapsed(state: HeartbeatState, *, policy: HeartbeatPolicy, now: str) -> bool:
    return _since_last_notice_seconds(state, now=now) < float(policy.repeat_interval_s)


def _since_last_notice_seconds(state: HeartbeatState, *, now: str) -> float:
    if state.last_notice_at is None:
        return 0.0
    try:
        return max(0.0, seconds_between(state.last_notice_at, now))
    except Exception:
        return 0.0


def _decision(action: HeartbeatAction, state: HeartbeatState, *, silence_seconds: float) -> HeartbeatDecision:
    return HeartbeatDecision(
        action=action,
        subject_kind=state.subject_kind,
        subject_id=state.subject_id,
        owner=state.owner,
        last_progress_at=state.last_progress_at,
        last_notice_at=state.last_notice_at,
        silence_seconds=silence_seconds,
        notice_count=state.notice_count,
    )


def _progress_advanced(observed: str, recorded: str) -> bool:
    if observed == recorded:
        return False
    try:
        return seconds_between(recorded, observed) > 0
    except Exception:
        return True
