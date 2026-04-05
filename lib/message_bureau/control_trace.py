from __future__ import annotations

from .reply_metadata import (
    reply_heartbeat_silence_seconds,
    reply_last_progress_at,
    reply_notice,
    reply_notice_kind,
)


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
    attempts = attempt_summaries_for_records(service, latest_attempts_for_message(service, message_id))
    replies = reply_summaries_for_records(service, service._reply_store.list_message(message_id))
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
        replies=reply_summaries_for_records(service, replies),
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
        replies=reply_summaries_for_records(service, replies),
        events=event_summaries_for_attempt(service, attempt),
        job=job,
        jobs=(job,),
    )


def trace_payload(
    service,
    *,
    target: str,
    resolved_kind: str,
    submission: dict[str, object] | None = None,
    message: dict[str, object] | None = None,
    attempt: dict[str, object] | None = None,
    reply: dict[str, object] | None = None,
    job: dict[str, object] | None = None,
    messages: tuple | list = (),
    attempts: tuple | list = (),
    replies: tuple | list = (),
    events: tuple | list = (),
    jobs: tuple | list = (),
) -> dict[str, object]:
    message_items = [message_summary(item) if not isinstance(item, dict) else item for item in messages]
    attempt_items = [attempt_summary(item) if not isinstance(item, dict) else item for item in attempts]
    reply_items = [reply_summary(item) if not isinstance(item, dict) else item for item in replies]
    event_items = [event_summary(service, item) if not isinstance(item, dict) else item for item in events]
    job_items = [job_summary(service, item) if not isinstance(item, dict) else item for item in jobs if item is not None]
    return {
        'target': target,
        'resolved_kind': resolved_kind,
        'submission_id': submission['submission_id'] if submission is not None else None,
        'message_id': message['message_id'] if message is not None else (message_items[0]['message_id'] if message_items else None),
        'attempt_id': attempt['attempt_id'] if attempt is not None else None,
        'reply_id': reply['reply_id'] if reply is not None else None,
        'job_id': job['job_id'] if job is not None else None,
        'submission': submission,
        'message': message,
        'attempt': attempt,
        'reply': reply,
        'job': job,
        'message_count': len(message_items),
        'attempt_count': len(attempt_items),
        'reply_count': len(reply_items),
        'event_count': len(event_items),
        'job_count': len(job_items),
        'messages': message_items,
        'attempts': attempt_items,
        'replies': reply_items,
        'events': event_items,
        'jobs': job_items,
    }


def latest_messages_for_submission(service, submission_id: str) -> list:
    latest: dict[str, object] = {}
    order: list[str] = []
    for record in service._message_store.list_submission(submission_id):
        if record.message_id not in latest:
            order.append(record.message_id)
        latest[record.message_id] = record
    return [latest[message_id] for message_id in order]


def latest_attempts_for_message(service, message_id: str) -> list:
    latest: dict[str, object] = {}
    order: list[str] = []
    for record in service._attempt_store.list_message(message_id):
        if record.attempt_id not in latest:
            order.append(record.attempt_id)
        latest[record.attempt_id] = record
    return [latest[attempt_id] for attempt_id in order]


def attempt_summaries_for_messages(service, messages: list) -> tuple[dict[str, object], ...]:
    items: list[dict[str, object]] = []
    for message in messages:
        items.extend(attempt_summaries_for_records(service, latest_attempts_for_message(service, message.message_id)))
    return tuple(items)


def attempt_summaries_for_records(service, attempts: list) -> tuple[dict[str, object], ...]:
    ordered = sorted(attempts, key=lambda item: (item.retry_index, item.started_at, item.attempt_id))
    return tuple(attempt_summary(item) for item in ordered)


def reply_summaries_for_messages(service, messages: list) -> tuple[dict[str, object], ...]:
    items: list[dict[str, object]] = []
    for message in messages:
        items.extend(reply_summaries_for_records(service, service._reply_store.list_message(message.message_id)))
    return tuple(items)


def reply_summaries_for_records(service, replies: list) -> tuple[dict[str, object], ...]:
    ordered = sorted(replies, key=lambda item: (item.finished_at, item.reply_id))
    return tuple(reply_summary(item) for item in ordered)


def event_summaries_for_messages(service, messages: tuple | list) -> tuple[dict[str, object], ...]:
    message_ids = {message.message_id for message in messages}
    latest: dict[str, object] = {}
    order: list[str] = []
    for agent_name in sorted(service._config.agents):
        for record in service._inbound_store.list_agent(agent_name):
            if record.message_id not in message_ids:
                continue
            if record.inbound_event_id not in latest:
                order.append(record.inbound_event_id)
            latest[record.inbound_event_id] = record
    events = [latest[event_id] for event_id in order]
    ordered = sorted(events, key=lambda item: (item.created_at, item.inbound_event_id))
    return tuple(event_summary(service, item) for item in ordered)


def event_summaries_for_attempt(service, attempt) -> tuple[dict[str, object], ...]:
    events = [
        event
        for event in event_summaries_for_messages(service, (service._message_store.get_latest(attempt.message_id),))
        if event['attempt_id'] == attempt.attempt_id
    ]
    return tuple(events)


def submission_summary_by_id(service, submission_id: str | None) -> dict[str, object] | None:
    if not submission_id:
        return None
    submission = service._submission_store.get_latest(submission_id)
    if submission is None:
        return None
    return submission_summary(submission)


def submission_summary(submission) -> dict[str, object]:
    return {
        'submission_id': submission.submission_id,
        'from_actor': submission.from_actor,
        'target_scope': submission.target_scope,
        'task_id': submission.task_id,
        'job_ids': list(submission.job_ids),
        'created_at': submission.created_at,
        'updated_at': submission.updated_at,
    }


def message_summary(message) -> dict[str, object]:
    return {
        'message_id': message.message_id,
        'origin_message_id': message.origin_message_id,
        'submission_id': message.submission_id,
        'from_actor': message.from_actor,
        'target_scope': message.target_scope,
        'target_agents': list(message.target_agents),
        'message_class': message.message_class,
        'message_state': message.message_state.value,
        'priority': message.priority,
        'reply_mode': message.reply_policy.get('mode'),
        'expected_reply_count': message.reply_policy.get('expected_reply_count'),
        'silence_on_success': bool(message.reply_policy.get('silence_on_success')),
        'retry_mode': message.retry_policy.get('mode'),
        'created_at': message.created_at,
        'updated_at': message.updated_at,
    }


def attempt_summary(attempt) -> dict[str, object]:
    return {
        'attempt_id': attempt.attempt_id,
        'message_id': attempt.message_id,
        'agent_name': attempt.agent_name,
        'provider': attempt.provider,
        'job_id': attempt.job_id,
        'retry_index': attempt.retry_index,
        'attempt_state': attempt.attempt_state.value,
        'health_snapshot_ref': attempt.health_snapshot_ref,
        'started_at': attempt.started_at,
        'updated_at': attempt.updated_at,
    }


def reply_summary(reply) -> dict[str, object]:
    return {
        'reply_id': reply.reply_id,
        'message_id': reply.message_id,
        'attempt_id': reply.attempt_id,
        'agent_name': reply.agent_name,
        'terminal_status': reply.terminal_status.value,
        'reply': reply.reply,
        'reply_preview': _preview_text(reply.reply),
        'reply_size': len(reply.reply or ''),
        'notice': reply_notice(reply),
        'notice_kind': reply_notice_kind(reply),
        'last_progress_at': reply_last_progress_at(reply),
        'heartbeat_silence_seconds': reply_heartbeat_silence_seconds(reply),
        'reason': reply.diagnostics.get('reason'),
        'status': reply.diagnostics.get('status'),
        'silence_on_success': bool(reply.diagnostics.get('silence_on_success')),
        'provider_turn_ref': reply.diagnostics.get('provider_turn_ref'),
        'finished_at': reply.finished_at,
    }


def event_summary(service, event) -> dict[str, object]:
    mailbox = service._mailbox_store.load(event.agent_name)
    return {
        'inbound_event_id': event.inbound_event_id,
        'agent_name': event.agent_name,
        'event_type': event.event_type.value,
        'message_id': event.message_id,
        'attempt_id': event.attempt_id,
        'payload_ref': event.payload_ref,
        'priority': event.priority,
        'status': event.status.value,
        'mailbox_state': mailbox.mailbox_state.value if mailbox is not None else None,
        'mailbox_active': bool(mailbox is not None and mailbox.active_inbound_event_id == event.inbound_event_id),
        'created_at': event.created_at,
        'started_at': event.started_at,
        'finished_at': event.finished_at,
    }


def job_summary(service, job_id: str, *, hint_agent: str | None = None) -> dict[str, object] | None:
    job = None
    if hint_agent:
        job = service._job_store.get_latest(hint_agent, job_id)
    if job is None:
        for agent_name in sorted(service._config.agents):
            if agent_name == hint_agent:
                continue
            job = service._job_store.get_latest(agent_name, job_id)
            if job is not None:
                break
    if job is None:
        return None
    return {
        'job_id': job.job_id,
        'agent_name': job.agent_name,
        'provider': job.provider,
        'status': job.status.value,
        'submission_id': job.submission_id,
        'created_at': job.created_at,
        'updated_at': job.updated_at,
    }


def _preview_text(value: str, *, limit: int = 120) -> str:
    text = str(value or '').replace('\r', '').replace('\n', '\\n').strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + '...'


__all__ = ['trace']
