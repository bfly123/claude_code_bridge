from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from ccbd.api_models import JobRecord, JobStatus, MessageEnvelope
from completion.models import CompletionDecision
from message_bureau.reply_payloads import compose_reply_payload
from mailbox_targets import normalize_mailbox_target
from mailbox_kernel import (
    InboundEventRecord,
    InboundEventStatus,
    InboundEventType,
)

from .facade_state import (
    next_retry_index,
    refresh_mailbox,
    refresh_message_state,
    resolve_origin_message_id,
    set_message_state,
)
from .models import AttemptRecord, AttemptState, MessageRecord, MessageState, ReplyRecord, ReplyTerminalStatus


def record_submission(
    service,
    request: MessageEnvelope,
    jobs: tuple[JobRecord, ...],
    *,
    submission_id: str | None,
    accepted_at: str,
    origin_message_id: str | None = None,
) -> str | None:
    if not jobs:
        return None
    message_id = new_id('msg')
    service._message_store.append(
        MessageRecord(
            message_id=message_id,
            origin_message_id=origin_message_id or resolve_origin_message_id(service, request.reply_to),
            from_actor=request.from_actor,
            target_scope=request.delivery_scope.value,
            target_agents=tuple(job.agent_name for job in jobs),
            message_class=request.message_type,
            reply_policy={
                'mode': 'all' if len(jobs) > 1 else 'single',
                'expected_reply_count': len(jobs),
                'silence_on_success': bool(request.silence_on_success),
            },
            retry_policy={
                'mode': 'auto',
                'max_attempts': 3,
                'retryable_reasons': ['api_error', 'transport_error'],
                'retry_runtime_when_resume_supported': True,
                'retryable_runtime_reasons': ['pane_dead', 'pane_unavailable'],
            },
            priority=100,
            payload_ref=None,
            submission_id=submission_id,
            created_at=accepted_at,
            updated_at=accepted_at,
            message_state=MessageState.QUEUED,
        )
    )
    for job in jobs:
        attempt_id = new_id('att')
        service._attempt_store.append(
            AttemptRecord(
                attempt_id=attempt_id,
                message_id=message_id,
                agent_name=job.agent_name,
                provider=job.provider,
                job_id=job.job_id,
                retry_index=0,
                health_snapshot_ref=None,
                started_at=accepted_at,
                updated_at=accepted_at,
                attempt_state=AttemptState.PENDING,
            )
        )
        service._inbound_store.append(
            InboundEventRecord(
                inbound_event_id=new_id('iev'),
                agent_name=job.agent_name,
                event_type=InboundEventType.TASK_REQUEST,
                message_id=message_id,
                attempt_id=attempt_id,
                payload_ref=f'job:{job.job_id}',
                priority=100,
                status=InboundEventStatus.QUEUED,
                created_at=accepted_at,
            )
        )
        refresh_mailbox(service, job.agent_name, updated_at=accepted_at)
    return message_id


def claimable_request_job_ids(service, agent_name: str) -> tuple[str, ...]:
    event = service._mailbox_kernel.peek_next(agent_name, event_type=InboundEventType.TASK_REQUEST)
    if event is None:
        return ()
    job_id = job_id_from_payload_ref(event.payload_ref)
    if not job_id:
        return ()
    return (job_id,)


def mark_attempt_started(service, job: JobRecord, *, started_at: str) -> None:
    attempt = service._attempt_store.get_latest_by_job_id(job.job_id)
    if attempt is None:
        return
    service._attempt_store.append(
        replace(
            attempt,
            started_at=attempt.started_at or started_at,
            updated_at=started_at,
            attempt_state=AttemptState.RUNNING,
        )
    )
    inbound = service._inbound_store.get_latest_for_attempt(job.agent_name, attempt.attempt_id)
    if inbound is not None and inbound.status not in {
        InboundEventStatus.CONSUMED,
        InboundEventStatus.SUPERSEDED,
        InboundEventStatus.ABANDONED,
    }:
        service._mailbox_kernel.claim(
            job.agent_name,
            inbound.inbound_event_id,
            started_at=started_at,
        )
    set_message_state(service, attempt.message_id, MessageState.RUNNING, updated_at=started_at)
    refresh_mailbox(service, job.agent_name, updated_at=started_at)


def record_attempt_terminal(service, job: JobRecord, decision: CompletionDecision, *, finished_at: str) -> None:
    attempt = service._attempt_store.get_latest_by_job_id(job.job_id)
    if attempt is None:
        return

    service._attempt_store.append(
        replace(
            attempt,
            updated_at=finished_at,
            attempt_state=attempt_state_for_status(job.status),
        )
    )

    inbound = service._inbound_store.get_latest_for_attempt(job.agent_name, attempt.attempt_id)
    if inbound is not None and inbound.status not in {
        InboundEventStatus.CONSUMED,
        InboundEventStatus.SUPERSEDED,
        InboundEventStatus.ABANDONED,
    }:
        if inbound.status in {InboundEventStatus.CREATED, InboundEventStatus.QUEUED} and job.status is JobStatus.CANCELLED:
            service._mailbox_kernel.abandon(job.agent_name, inbound.inbound_event_id, finished_at=finished_at)
        else:
            service._mailbox_kernel.consume(job.agent_name, inbound.inbound_event_id, finished_at=finished_at)
    else:
        refresh_mailbox(service, job.agent_name, updated_at=finished_at)

    refresh_message_state(service, attempt.message_id, updated_at=finished_at)


def record_reply(
    service,
    job: JobRecord,
    decision: CompletionDecision,
    *,
    finished_at: str,
    deliver_to_caller: bool = True,
) -> str | None:
    attempt = service._attempt_store.get_latest_by_job_id(job.job_id)
    if attempt is None:
        return None

    reply_text = delivered_reply_text(job, decision)
    reply_id = new_id('rep')
    service._reply_store.append(
        ReplyRecord(
            reply_id=reply_id,
            message_id=attempt.message_id,
            attempt_id=attempt.attempt_id,
            agent_name=job.agent_name,
            terminal_status=reply_status_for_job(job.status),
            reply=reply_text,
            diagnostics={
                'reason': decision.reason,
                'status': job.status.value,
                'provider_turn_ref': decision.provider_turn_ref,
                'decision_diagnostics': dict(decision.diagnostics or {}),
                'silence_on_success': bool(job.request.silence_on_success),
            },
            finished_at=finished_at,
        )
    )

    caller_mailbox = mailbox_actor(service, job.request.from_actor) if deliver_to_caller else None
    if caller_mailbox is not None:
        service._inbound_store.append(
            InboundEventRecord(
                inbound_event_id=new_id('iev'),
                agent_name=caller_mailbox,
                event_type=InboundEventType.TASK_REPLY,
                message_id=attempt.message_id,
                attempt_id=attempt.attempt_id,
                payload_ref=compose_reply_payload(reply_id),
                priority=10,
                status=InboundEventStatus.QUEUED,
                created_at=finished_at,
            )
        )
        refresh_mailbox(service, caller_mailbox, updated_at=finished_at)

    refresh_message_state(service, attempt.message_id, updated_at=finished_at)
    return reply_id


def record_notice(
    service,
    job: JobRecord,
    *,
    reply: str,
    diagnostics: dict[str, object] | None,
    finished_at: str,
    terminal_status: ReplyTerminalStatus = ReplyTerminalStatus.INCOMPLETE,
    deliver_to_actor: str | None = None,
) -> str | None:
    attempt = service._attempt_store.get_latest_by_job_id(job.job_id)
    if attempt is None:
        return None

    reply_id = new_id('rep')
    payload = dict(diagnostics or {})
    payload.setdefault('status', job.status.value)
    payload.setdefault('notice', True)
    service._reply_store.append(
        ReplyRecord(
            reply_id=reply_id,
            message_id=attempt.message_id,
            attempt_id=attempt.attempt_id,
            agent_name=job.agent_name,
            terminal_status=terminal_status,
            reply=reply or '',
            diagnostics=payload,
            finished_at=finished_at,
        )
    )

    target_actor = deliver_to_actor if deliver_to_actor is not None else job.request.from_actor
    caller_mailbox = mailbox_actor(service, target_actor)
    if caller_mailbox is not None:
        service._inbound_store.append(
            InboundEventRecord(
                inbound_event_id=new_id('iev'),
                agent_name=caller_mailbox,
                event_type=InboundEventType.TASK_REPLY,
                message_id=attempt.message_id,
                attempt_id=attempt.attempt_id,
                payload_ref=compose_reply_payload(reply_id),
                priority=10,
                status=InboundEventStatus.QUEUED,
                created_at=finished_at,
            )
        )
        refresh_mailbox(service, caller_mailbox, updated_at=finished_at)

    refresh_message_state(service, attempt.message_id, updated_at=finished_at)
    return reply_id


def record_terminal(
    service,
    job: JobRecord,
    decision: CompletionDecision,
    *,
    finished_at: str,
    deliver_to_caller: bool = True,
    record_reply_enabled: bool = True,
) -> str | None:
    record_attempt_terminal(service, job, decision, finished_at=finished_at)
    if not record_reply_enabled:
        return None
    return record_reply(service, job, decision, finished_at=finished_at, deliver_to_caller=deliver_to_caller)


def record_retry_attempt(service, message_id: str, job: JobRecord, *, accepted_at: str) -> str:
    message = service._message_store.get_latest(message_id)
    if message is None:
        raise ValueError(f'message not found: {message_id}')
    retry_index = next_retry_index(service, message_id, job.agent_name)
    attempt_id = new_id('att')
    service._attempt_store.append(
        AttemptRecord(
            attempt_id=attempt_id,
            message_id=message_id,
            agent_name=job.agent_name,
            provider=job.provider,
            job_id=job.job_id,
            retry_index=retry_index,
            health_snapshot_ref=None,
            started_at=accepted_at,
            updated_at=accepted_at,
            attempt_state=AttemptState.PENDING,
        )
    )
    service._inbound_store.append(
        InboundEventRecord(
            inbound_event_id=new_id('iev'),
            agent_name=job.agent_name,
            event_type=InboundEventType.TASK_REQUEST,
            message_id=message_id,
            attempt_id=attempt_id,
            payload_ref=f'job:{job.job_id}',
            priority=100,
            status=InboundEventStatus.QUEUED,
            created_at=accepted_at,
        )
    )
    set_message_state(service, message_id, MessageState.QUEUED, updated_at=accepted_at)
    refresh_mailbox(service, job.agent_name, updated_at=accepted_at)
    return attempt_id


def job_id_from_payload_ref(payload_ref: str | None) -> str | None:
    text = str(payload_ref or '').strip()
    if not text.startswith('job:'):
        return None
    job_id = text.split(':', 1)[1].strip()
    if not job_id:
        return None
    return job_id


def mailbox_actor(service, actor: str) -> str | None:
    return normalize_mailbox_target(actor, known_targets=service._known_mailboxes)


def attempt_state_for_status(status: JobStatus) -> AttemptState:
    mapping = {
        JobStatus.COMPLETED: AttemptState.COMPLETED,
        JobStatus.FAILED: AttemptState.FAILED,
        JobStatus.INCOMPLETE: AttemptState.INCOMPLETE,
        JobStatus.CANCELLED: AttemptState.CANCELLED,
    }
    return mapping.get(status, AttemptState.INCOMPLETE)


def reply_status_for_job(status: JobStatus) -> ReplyTerminalStatus:
    mapping = {
        JobStatus.COMPLETED: ReplyTerminalStatus.COMPLETED,
        JobStatus.FAILED: ReplyTerminalStatus.FAILED,
        JobStatus.INCOMPLETE: ReplyTerminalStatus.INCOMPLETE,
        JobStatus.CANCELLED: ReplyTerminalStatus.CANCELLED,
    }
    return mapping.get(status, ReplyTerminalStatus.INCOMPLETE)


def delivered_reply_text(job: JobRecord, decision: CompletionDecision) -> str:
    if job.status is not JobStatus.COMPLETED:
        return decision.reply or ''
    if not bool(job.request.silence_on_success):
        return decision.reply or ''
    parts = [
        'CCB_COMPLETE',
        f'from={job.agent_name}',
        f'status={job.status.value}',
        f'job={job.job_id}',
    ]
    task_id = str(job.request.task_id or '').strip()
    if task_id:
        parts.append(f'task={task_id}')
    parts.append('result=hidden')
    return ' '.join(parts)


def new_id(prefix: str) -> str:
    return f'{prefix}_{uuid4().hex[:12]}'


__all__ = [
    'claimable_request_job_ids',
    'mark_attempt_started',
    'record_notice',
    'record_attempt_terminal',
    'record_reply',
    'record_retry_attempt',
    'record_submission',
    'record_terminal',
]
