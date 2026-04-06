from __future__ import annotations

from collections.abc import Mapping


def render_trace(payload: Mapping[str, object]) -> tuple[str, ...]:
    lines: list[str] = list(_trace_header_lines(payload))
    submission = payload.get('submission')
    if isinstance(submission, Mapping):
        lines.append(_submission_line(submission))
    for message in payload.get('messages') or ():
        lines.append(_message_line(message))
    for attempt in payload.get('attempts') or ():
        lines.append(_attempt_line(attempt))
    for reply in payload.get('replies') or ():
        lines.append(_reply_line(reply))
    for event in payload.get('events') or ():
        lines.append(_event_line(event))
    for job in payload.get('jobs') or ():
        lines.append(_job_line(job))
    return tuple(lines)


def _trace_header_lines(payload: Mapping[str, object]) -> tuple[str, ...]:
    fields = (
        ('target', payload.get('target')),
        ('resolved_kind', payload.get('resolved_kind')),
        ('submission_id', payload.get('submission_id')),
        ('message_id', payload.get('message_id')),
        ('attempt_id', payload.get('attempt_id')),
        ('reply_id', payload.get('reply_id')),
        ('job_id', payload.get('job_id')),
        ('message_count', payload.get('message_count')),
        ('attempt_count', payload.get('attempt_count')),
        ('reply_count', payload.get('reply_count')),
        ('event_count', payload.get('event_count')),
        ('job_count', payload.get('job_count')),
    )
    return ('trace_status: ok', *(f'{name}: {value}' for name, value in fields))


def _submission_line(submission: Mapping[str, object]) -> str:
    return (
        'submission: '
        f'id={submission.get("submission_id")} from={submission.get("from_actor")} '
        f'scope={submission.get("target_scope")} task={submission.get("task_id")} '
        f'jobs={len(submission.get("job_ids") or [])} '
        f'created={submission.get("created_at")} updated={submission.get("updated_at")}'
    )


def _message_line(message) -> str:
    targets = ','.join(message.get('target_agents') or [])
    return (
        'message: '
        f'id={message.get("message_id")} submission={message.get("submission_id")} '
        f'origin={message.get("origin_message_id")} '
        f'from={message.get("from_actor")} scope={message.get("target_scope")} '
        f'targets={targets} class={message.get("message_class")} '
        f'state={message.get("message_state")} priority={message.get("priority")} '
        f'created={message.get("created_at")} updated={message.get("updated_at")}'
    )


def _attempt_line(attempt) -> str:
    return (
        'attempt: '
        f'id={attempt.get("attempt_id")} message={attempt.get("message_id")} '
        f'agent={attempt.get("agent_name")} provider={attempt.get("provider")} '
        f'job={attempt.get("job_id")} retry={attempt.get("retry_index")} '
        f'state={attempt.get("attempt_state")} started={attempt.get("started_at")} '
        f'updated={attempt.get("updated_at")}'
    )


def _reply_line(reply) -> str:
    return (
        'reply: '
        f'id={reply.get("reply_id")} message={reply.get("message_id")} '
        f'attempt={reply.get("attempt_id")} agent={reply.get("agent_name")} '
        f'terminal={reply.get("terminal_status")} size={reply.get("reply_size")} '
        f'notice={str(bool(reply.get("notice"))).lower()} kind={reply.get("notice_kind")} '
        f'reason={reply.get("reason")} finished={reply.get("finished_at")} '
        f'preview={reply.get("reply_preview")}'
    )


def _event_line(event) -> str:
    return (
        'event: '
        f'id={event.get("inbound_event_id")} agent={event.get("agent_name")} '
        f'type={event.get("event_type")} status={event.get("status")} '
        f'mailbox_state={event.get("mailbox_state")} active={str(bool(event.get("mailbox_active"))).lower()} '
        f'message={event.get("message_id")} attempt={event.get("attempt_id")} '
        f'created={event.get("created_at")} finished={event.get("finished_at")}'
    )


def _job_line(job) -> str:
    return (
        'job: '
        f'id={job.get("job_id")} agent={job.get("agent_name")} provider={job.get("provider")} '
        f'status={job.get("status")} submission={job.get("submission_id")} '
        f'created={job.get("created_at")} updated={job.get("updated_at")}'
    )


__all__ = ['render_trace']
