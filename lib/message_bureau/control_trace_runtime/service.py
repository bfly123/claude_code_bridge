from __future__ import annotations

from .collections import (
    attempt_summaries_for_messages,
    attempt_summaries_for_records,
    event_summaries_for_attempt,
    event_summaries_for_messages,
    latest_attempts_for_message,
    latest_messages_for_submission,
    reply_summaries_for_messages,
    reply_summaries_for_records,
    submission_summary_by_id,
    trace_payload,
)
from .summaries import attempt_summary, job_summary, message_summary, reply_summary, submission_summary


def trace(service, target: str) -> dict[str, object]:
    identifier = str(target or '').strip()
    if not identifier:
        raise ValueError('trace requires target')
    if identifier.startswith('sub_'):
        return trace_submission(service, identifier)
    if identifier.startswith('msg_'):
        return trace_message(service, identifier, resolved_kind='message')
    if identifier.startswith('att_'):
        return trace_attempt(service, identifier)
    if identifier.startswith('rep_'):
        return trace_reply(service, identifier)
    if identifier.startswith('job_'):
        return trace_job(service, identifier)
    raise ValueError('trace requires <submission_id|message_id|attempt_id|reply_id|job_id>')


def trace_submission(service, submission_id: str) -> dict[str, object]:
    submission = service._submission_store.get_latest(submission_id)
    if submission is None:
        raise ValueError(f'submission not found: {submission_id}')
    messages = latest_messages_for_submission(service, submission_id)
    attempts = attempt_summaries_for_messages(service, messages)
    replies = reply_summaries_for_messages(service, messages)
    jobs = [job_summary(service, job_id) for job_id in submission.job_ids]
    events = event_summaries_for_messages(service, messages)
    return trace_payload(
        service,
        target=submission_id,
        resolved_kind='submission',
        submission=submission_summary(submission),
        messages=messages,
        attempts=attempts,
        replies=replies,
        events=events,
        jobs=jobs,
    )


def trace_message(service, message_id: str, *, resolved_kind: str) -> dict[str, object]:
    message = service._message_store.get_latest(message_id)
    if message is None:
        raise ValueError(f'message not found: {message_id}')
    attempts = attempt_summaries_for_records(latest_attempts_for_message(service, message_id))
    replies = reply_summaries_for_records(service._reply_store.list_message(message_id))
    events = event_summaries_for_messages(service, (message,))
    jobs = [job_summary(service, item['job_id'], hint_agent=item['agent_name']) for item in attempts if item['job_id']]
    submission = submission_summary_by_id(service, message.submission_id)
    return trace_payload(
        service,
        target=message_id,
        resolved_kind=resolved_kind,
        submission=submission,
        message=message_summary(message),
        messages=(message,),
        attempts=attempts,
        replies=replies,
        events=events,
        jobs=jobs,
    )


def trace_attempt(service, attempt_id: str) -> dict[str, object]:
    attempt = service._attempt_store.get_latest(attempt_id)
    if attempt is None:
        raise ValueError(f'attempt not found: {attempt_id}')
    message = service._message_store.get_latest(attempt.message_id)
    if message is None:
        raise ValueError(f'message not found for attempt: {attempt_id}')
    replies = [record for record in service._reply_store.list_message(message.message_id) if record.attempt_id == attempt_id]
    return trace_payload(
        service,
        target=attempt_id,
        resolved_kind='attempt',
        submission=submission_summary_by_id(service, message.submission_id),
        message=message_summary(message),
        attempt=attempt_summary(attempt),
        messages=(message,),
        attempts=(attempt_summary(attempt),),
        replies=reply_summaries_for_records(replies),
        events=event_summaries_for_attempt(service, attempt),
        jobs=(job_summary(service, attempt.job_id, hint_agent=attempt.agent_name),),
    )


def trace_reply(service, reply_id: str) -> dict[str, object]:
    reply = service._reply_store.get_latest(reply_id)
    if reply is None:
        raise ValueError(f'reply not found: {reply_id}')
    attempt = service._attempt_store.get_latest(reply.attempt_id)
    message = service._message_store.get_latest(reply.message_id)
    if attempt is None or message is None:
        raise ValueError(f'trace chain is incomplete for reply: {reply_id}')
    return trace_payload(
        service,
        target=reply_id,
        resolved_kind='reply',
        submission=submission_summary_by_id(service, message.submission_id),
        message=message_summary(message),
        attempt=attempt_summary(attempt),
        reply=reply_summary(reply),
        messages=(message,),
        attempts=(attempt_summary(attempt),),
        replies=(reply_summary(reply),),
        events=event_summaries_for_attempt(service, attempt),
        jobs=(job_summary(service, attempt.job_id, hint_agent=attempt.agent_name),),
    )


def trace_job(service, job_id: str) -> dict[str, object]:
    attempt = service._attempt_store.get_latest_by_job_id(job_id)
    if attempt is None:
        raise ValueError(f'job not found in message bureau: {job_id}')
    message = service._message_store.get_latest(attempt.message_id)
    if message is None:
        raise ValueError(f'message not found for job: {job_id}')
    replies = [record for record in service._reply_store.list_message(message.message_id) if record.attempt_id == attempt.attempt_id]
    job = job_summary(service, job_id, hint_agent=attempt.agent_name)
    return trace_payload(
        service,
        target=job_id,
        resolved_kind='job',
        submission=submission_summary_by_id(service, message.submission_id),
        message=message_summary(message),
        attempt=attempt_summary(attempt),
        messages=(message,),
        attempts=(attempt_summary(attempt),),
        replies=reply_summaries_for_records(replies),
        events=event_summaries_for_attempt(service, attempt),
        job=job,
        jobs=(job,),
    )


__all__ = ['trace']
