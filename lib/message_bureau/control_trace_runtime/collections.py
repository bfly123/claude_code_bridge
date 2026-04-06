from __future__ import annotations

from .summaries import (
    attempt_summary,
    event_summary,
    message_summary,
    reply_summary,
    submission_summary,
)


def latest_messages_for_submission(service, submission_id: str) -> list:
    return _latest_records(
        service._message_store.list_submission(submission_id),
        key_fn=lambda record: record.message_id,
    )


def latest_attempts_for_message(service, message_id: str) -> list:
    return _latest_records(
        service._attempt_store.list_message(message_id),
        key_fn=lambda record: record.attempt_id,
    )


def attempt_summaries_for_messages(service, messages: list) -> tuple[dict[str, object], ...]:
    items: list[dict[str, object]] = []
    for message in messages:
        attempts = latest_attempts_for_message(service, message.message_id)
        items.extend(attempt_summaries_for_records(attempts))
    return tuple(items)


def attempt_summaries_for_records(attempts: list) -> tuple[dict[str, object], ...]:
    ordered = sorted(
        attempts,
        key=lambda item: (item.retry_index, item.started_at, item.attempt_id),
    )
    return tuple(attempt_summary(item) for item in ordered)


def reply_summaries_for_messages(service, messages: list) -> tuple[dict[str, object], ...]:
    items: list[dict[str, object]] = []
    for message in messages:
        replies = service._reply_store.list_message(message.message_id)
        items.extend(reply_summaries_for_records(replies))
    return tuple(items)


def reply_summaries_for_records(replies: list) -> tuple[dict[str, object], ...]:
    ordered = sorted(replies, key=lambda item: (item.finished_at, item.reply_id))
    return tuple(reply_summary(item) for item in ordered)


def event_summaries_for_messages(service, messages: tuple | list) -> tuple[dict[str, object], ...]:
    message_ids = {message.message_id for message in messages}
    events = _latest_records(
        _matching_events(service, message_ids=message_ids),
        key_fn=lambda record: record.inbound_event_id,
    )
    ordered = sorted(events, key=lambda item: (item.created_at, item.inbound_event_id))
    return tuple(event_summary(service, item) for item in ordered)


def event_summaries_for_attempt(service, attempt) -> tuple[dict[str, object], ...]:
    message = service._message_store.get_latest(attempt.message_id)
    if message is None:
        return ()
    events = [
        event
        for event in event_summaries_for_messages(service, (message,))
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
    message_items = _summary_items(messages, summary_fn=message_summary)
    attempt_items = _summary_items(attempts, summary_fn=attempt_summary)
    reply_items = _summary_items(replies, summary_fn=reply_summary)
    event_items = _summary_items(events, summary_fn=lambda item: event_summary(service, item))
    job_items = [item for item in jobs if item is not None]
    message_id = _selected_message_id(message, message_items)
    return {
        'target': target,
        'resolved_kind': resolved_kind,
        'submission_id': submission['submission_id'] if submission is not None else None,
        'message_id': message_id,
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


def _latest_records(records, *, key_fn) -> list:
    latest: dict[str, object] = {}
    order: list[str] = []
    for record in records:
        record_id = key_fn(record)
        if record_id not in latest:
            order.append(record_id)
        latest[record_id] = record
    return [latest[record_id] for record_id in order]


def _matching_events(service, *, message_ids: set[str]):
    for agent_name in sorted(service._config.agents):
        for record in service._inbound_store.list_agent(agent_name):
            if record.message_id in message_ids:
                yield record


def _summary_items(records, *, summary_fn) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for item in records:
        items.append(item if isinstance(item, dict) else summary_fn(item))
    return items


def _selected_message_id(
    message: dict[str, object] | None,
    message_items: list[dict[str, object]],
) -> object | None:
    if message is not None:
        return message['message_id']
    if message_items:
        return message_items[0]['message_id']
    return None


__all__ = [
    'attempt_summaries_for_messages',
    'attempt_summaries_for_records',
    'event_summaries_for_attempt',
    'event_summaries_for_messages',
    'latest_attempts_for_message',
    'latest_messages_for_submission',
    'reply_summaries_for_messages',
    'reply_summaries_for_records',
    'submission_summary_by_id',
    'trace_payload',
]
