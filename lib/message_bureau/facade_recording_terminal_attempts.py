from __future__ import annotations

from dataclasses import replace

from ccbd.api_models import JobRecord, JobStatus
from completion.models import CompletionDecision
from mailbox_kernel import InboundEventStatus

from .facade_recording_common import attempt_state_for_status
from .facade_state import refresh_mailbox, refresh_message_state, set_message_state
from .models import AttemptState, MessageState

_TERMINAL_INBOUND_STATUSES = {
    InboundEventStatus.CONSUMED,
    InboundEventStatus.SUPERSEDED,
    InboundEventStatus.ABANDONED,
}


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
    if inbound is not None and inbound.status not in _TERMINAL_INBOUND_STATUSES:
        service._mailbox_kernel.claim(
            job.agent_name,
            inbound.inbound_event_id,
            started_at=started_at,
        )
    set_message_state(service, attempt.message_id, MessageState.RUNNING, updated_at=started_at)
    refresh_mailbox(service, job.agent_name, updated_at=started_at)


def record_attempt_terminal(service, job: JobRecord, decision: CompletionDecision, *, finished_at: str) -> None:
    del decision
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
    if inbound is not None and inbound.status not in _TERMINAL_INBOUND_STATUSES:
        if inbound.status in {InboundEventStatus.CREATED, InboundEventStatus.QUEUED} and job.status is JobStatus.CANCELLED:
            service._mailbox_kernel.abandon(job.agent_name, inbound.inbound_event_id, finished_at=finished_at)
        else:
            service._mailbox_kernel.consume(job.agent_name, inbound.inbound_event_id, finished_at=finished_at)
    else:
        refresh_mailbox(service, job.agent_name, updated_at=finished_at)

    refresh_message_state(service, attempt.message_id, updated_at=finished_at)


__all__ = [
    'mark_attempt_started',
    'record_attempt_terminal',
]
