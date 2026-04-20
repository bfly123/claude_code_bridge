from __future__ import annotations

from ccbd.api_models import JobRecord, MessageEnvelope
from mailbox_kernel import InboundEventRecord, InboundEventStatus, InboundEventType

from .facade_recording_common import job_id_from_payload_ref, new_id
from .facade_state import next_retry_index, refresh_mailbox, resolve_origin_message_id, set_message_state
from .models import AttemptRecord, AttemptState, MessageRecord, MessageState


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


__all__ = ['claimable_request_job_ids', 'record_retry_attempt', 'record_submission']
