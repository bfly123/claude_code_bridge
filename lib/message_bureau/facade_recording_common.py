from __future__ import annotations

from uuid import uuid4

from ccbd.api_models import JobRecord, JobStatus
from completion.models import CompletionDecision
from mailbox_runtime.targets import normalize_mailbox_target

from .models import AttemptState, ReplyTerminalStatus


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
    'attempt_state_for_status',
    'delivered_reply_text',
    'job_id_from_payload_ref',
    'mailbox_actor',
    'new_id',
    'reply_status_for_job',
]
