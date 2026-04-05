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
    progress_at = str(observed_last_progress_at or '').strip() or str(now or '').strip()
    if not progress_at:
        raise ValueError('observed_last_progress_at cannot be empty')
    current = state
    if current is None:
        current = HeartbeatState(
            subject_kind=subject_kind,
            subject_id=subject_id,
            owner=owner,
            last_progress_at=progress_at,
            last_notice_at=None,
            heartbeat_started_at=None,
            notice_count=0,
            updated_at=now,
        )

    base = replace(
        current,
        subject_kind=subject_kind,
        subject_id=subject_id,
        owner=owner,
    )
    heartbeat_active = current.notice_count > 0 or current.last_notice_at is not None
    progress_advanced = _progress_advanced(progress_at, current.last_progress_at)
    if progress_advanced and heartbeat_active:
        next_state = replace(
            base,
            last_progress_at=progress_at,
            last_notice_at=None,
            heartbeat_started_at=None,
            notice_count=0,
            updated_at=now,
        )
        return next_state, _decision(HeartbeatAction.RESET, next_state, silence_seconds=0.0)

    base = replace(base, last_progress_at=progress_at)

    try:
        silence_seconds = max(0.0, seconds_between(progress_at, now))
    except Exception:
        silence_seconds = 0.0
    if silence_seconds < float(policy.silence_start_after_s):
        next_state = replace(base, last_progress_at=progress_at)
        return next_state, _decision(HeartbeatAction.IDLE, next_state, silence_seconds=silence_seconds)

    if base.last_notice_at is None or base.notice_count <= 0:
        next_state = replace(
            base,
            last_progress_at=progress_at,
            last_notice_at=now,
            heartbeat_started_at=base.heartbeat_started_at or now,
            notice_count=1,
            updated_at=now,
        )
        return next_state, _decision(HeartbeatAction.ENTER, next_state, silence_seconds=silence_seconds)

    max_notice_count = policy.max_notice_count
    if max_notice_count is not None and base.notice_count >= int(max_notice_count):
        return base, _decision(HeartbeatAction.IDLE, base, silence_seconds=silence_seconds)

    try:
        since_last_notice = max(0.0, seconds_between(base.last_notice_at, now))
    except Exception:
        since_last_notice = 0.0
    if since_last_notice < float(policy.repeat_interval_s):
        return base, _decision(HeartbeatAction.IDLE, base, silence_seconds=silence_seconds)

    next_state = replace(
        base,
        last_progress_at=progress_at,
        last_notice_at=now,
        heartbeat_started_at=base.heartbeat_started_at or now,
        notice_count=base.notice_count + 1,
        updated_at=now,
    )
    return next_state, _decision(HeartbeatAction.REPEAT, next_state, silence_seconds=silence_seconds)


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


__all__ = ['evaluate_heartbeat']
