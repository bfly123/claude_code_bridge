from __future__ import annotations

from heartbeat import HeartbeatAction, HeartbeatPolicy, HeartbeatState, evaluate_heartbeat


def test_evaluate_heartbeat_enters_and_repeats_after_silence() -> None:
    policy = HeartbeatPolicy(silence_start_after_s=600.0, repeat_interval_s=600.0)

    idle_state, idle_decision = evaluate_heartbeat(
        policy=policy,
        subject_kind='job_progress',
        subject_id='job_1',
        owner='agent1',
        observed_last_progress_at='2026-04-04T00:00:00Z',
        now='2026-04-04T00:09:59Z',
        state=None,
    )
    assert idle_decision.action is HeartbeatAction.IDLE

    entered_state, entered_decision = evaluate_heartbeat(
        policy=policy,
        subject_kind='job_progress',
        subject_id='job_1',
        owner='agent1',
        observed_last_progress_at='2026-04-04T00:00:00Z',
        now='2026-04-04T00:10:00Z',
        state=idle_state,
    )
    assert entered_decision.action is HeartbeatAction.ENTER
    assert entered_decision.notice_due is True
    assert entered_state.notice_count == 1

    repeated_state, repeated_decision = evaluate_heartbeat(
        policy=policy,
        subject_kind='job_progress',
        subject_id='job_1',
        owner='agent1',
        observed_last_progress_at='2026-04-04T00:00:00Z',
        now='2026-04-04T00:20:00Z',
        state=entered_state,
    )
    assert repeated_decision.action is HeartbeatAction.REPEAT
    assert repeated_decision.notice_due is True
    assert repeated_state.notice_count == 2


def test_evaluate_heartbeat_can_enter_after_unpersisted_idle_progress_advance() -> None:
    policy = HeartbeatPolicy(silence_start_after_s=600.0, repeat_interval_s=600.0)
    active_state = HeartbeatState(
        subject_kind='job_progress',
        subject_id='job_1',
        owner='agent1',
        last_progress_at='2026-04-04T00:00:00Z',
        last_notice_at='2026-04-04T00:10:00Z',
        heartbeat_started_at='2026-04-04T00:10:00Z',
        notice_count=1,
        updated_at='2026-04-04T00:10:00Z',
    )

    reset_state, reset_decision = evaluate_heartbeat(
        policy=policy,
        subject_kind='job_progress',
        subject_id='job_1',
        owner='agent1',
        observed_last_progress_at='2026-04-04T00:12:00Z',
        now='2026-04-04T00:12:00Z',
        state=active_state,
    )
    assert reset_decision.action is HeartbeatAction.RESET
    assert reset_state.notice_count == 0
    assert reset_state.last_notice_at is None

    idle_state, idle_decision = evaluate_heartbeat(
        policy=policy,
        subject_kind='job_progress',
        subject_id='job_1',
        owner='agent1',
        observed_last_progress_at='2026-04-04T00:13:00Z',
        now='2026-04-04T00:13:00Z',
        state=reset_state,
    )
    assert idle_decision.action is HeartbeatAction.IDLE

    entered_state, entered_decision = evaluate_heartbeat(
        policy=policy,
        subject_kind='job_progress',
        subject_id='job_1',
        owner='agent1',
        observed_last_progress_at='2026-04-04T00:13:00Z',
        now='2026-04-04T00:24:00Z',
        state=reset_state,
    )
    assert idle_state.last_progress_at == '2026-04-04T00:13:00Z'
    assert entered_decision.action is HeartbeatAction.ENTER
    assert entered_decision.notice_due is True
    assert entered_state.notice_count == 1
