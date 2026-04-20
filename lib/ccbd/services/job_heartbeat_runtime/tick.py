from __future__ import annotations

from heartbeat import HeartbeatAction, evaluate_heartbeat
from mailbox_runtime.targets import known_mailbox_targets, normalize_mailbox_target

from .common import heartbeat_diagnostics, heartbeat_notice_body, snapshot_is_terminal
from .models import HeartbeatTickContext


def tick_job_heartbeat(service, dispatcher, job) -> bool:
    context = build_heartbeat_tick_context(service, dispatcher, job)
    if context is None:
        return False
    if context.decision.action is HeartbeatAction.RESET:
        return handle_reset_heartbeat(service, dispatcher, job, context)
    if not context.decision.notice_due:
        return True
    return deliver_heartbeat_notice(service, dispatcher, job, context)


def build_heartbeat_tick_context(service, dispatcher, job) -> HeartbeatTickContext | None:
    snapshot = dispatcher.get_snapshot(job.job_id)
    if snapshot_is_terminal(snapshot):
        service._store.remove(service._subject_kind, job.job_id)
        return None
    observed_last_progress_at = (
        str(snapshot.updated_at).strip()
        if snapshot is not None and str(snapshot.updated_at).strip()
        else str(job.updated_at).strip()
    )
    if not observed_last_progress_at:
        return None
    prior_state = service._store.load(service._subject_kind, job.job_id)
    now = service._clock()
    next_state, decision = evaluate_heartbeat(
        policy=service._policy,
        subject_kind=service._subject_kind,
        subject_id=job.job_id,
        owner=job.agent_name,
        observed_last_progress_at=observed_last_progress_at,
        now=now,
        state=prior_state,
    )
    return HeartbeatTickContext(
        snapshot=snapshot,
        observed_last_progress_at=observed_last_progress_at,
        now=now,
        next_state=next_state,
        decision=decision,
    )


def handle_reset_heartbeat(service, dispatcher, job, context: HeartbeatTickContext) -> bool:
    service._store.save(context.next_state)
    dispatcher._append_event(
        job,
        'job_heartbeat_reset',
        {
            'subject_kind': service._subject_kind,
            'action': context.decision.action.value,
            'notice_count': context.decision.notice_count,
            'last_progress_at': context.decision.last_progress_at,
        },
        timestamp=context.now,
    )
    return True


def deliver_heartbeat_notice(service, dispatcher, job, context: HeartbeatTickContext) -> bool:
    mailbox_target = normalize_mailbox_target(
        job.request.from_actor,
        known_targets=known_mailbox_targets(dispatcher._config),
    )
    diagnostics = heartbeat_diagnostics(
        job,
        decision=context.decision,
        snapshot=context.snapshot,
        mailbox_target=mailbox_target,
        subject_kind=service._subject_kind,
    )
    if dispatcher._message_bureau is None or mailbox_target is None:
        service._store.save(context.next_state)
        dispatcher._append_event(
            job,
            'job_heartbeat_skipped_no_mailbox',
            diagnostics,
            timestamp=context.now,
        )
        return True

    reply_id = dispatcher._message_bureau.record_notice(
        job,
        reply=heartbeat_notice_body(
            job,
            decision=context.decision,
            snapshot=context.snapshot,
        ),
        diagnostics=diagnostics,
        finished_at=context.now,
        deliver_to_actor=mailbox_target,
    )
    service._store.save(context.next_state)
    dispatcher._append_event(
        job,
        'job_heartbeat_notice_sent',
        {
            **diagnostics,
            'reply_id': reply_id,
        },
        timestamp=context.now,
    )
    return True


__all__ = [
    'build_heartbeat_tick_context',
    'deliver_heartbeat_notice',
    'handle_reset_heartbeat',
    'tick_job_heartbeat',
]
