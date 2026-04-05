from __future__ import annotations

from mailbox_targets import COMMAND_MAILBOX_ACTOR, normalize_mailbox_target
from mailbox_kernel import InboundEventStatus, InboundEventType, MailboxState
from message_bureau.reply_metadata import (
    reply_heartbeat_silence_seconds,
    reply_last_progress_at,
    reply_notice,
    reply_notice_kind,
)
from message_bureau.reply_payloads import delivery_job_id_from_payload, reply_id_from_payload

_TERMINAL_EVENT_STATES = frozenset(
    {
        InboundEventStatus.CONSUMED,
        InboundEventStatus.SUPERSEDED,
        InboundEventStatus.ABANDONED,
    }
)


def queue_summary(service, target: str = 'all') -> dict[str, object]:
    normalized = str(target or '').strip().lower() or 'all'
    if normalized == 'all':
        agent_summaries = [agent_queue(service, agent_name) for agent_name in _summary_targets(service)]
        return {
            'target': 'all',
            'agent_count': len(agent_summaries),
            'queued_agent_count': sum(1 for item in agent_summaries if int(item['queue_depth']) > 0),
            'active_agent_count': sum(1 for item in agent_summaries if item['active_inbound_event_id'] is not None),
            'total_queue_depth': sum(int(item['queue_depth']) for item in agent_summaries),
            'total_pending_reply_count': sum(int(item['pending_reply_count']) for item in agent_summaries),
            'agents': agent_summaries,
        }
    return {'target': normalized, 'agent': agent_queue(service, normalized)}


def agent_queue(service, agent_name: str) -> dict[str, object]:
    normalized = _require_mailbox_target(service, agent_name)

    mailbox = service._mailbox_store.load(normalized)
    events = pending_events(service, normalized)
    event_index = {event['inbound_event_id']: event for event in events}
    active = None
    active_event_id = mailbox.active_inbound_event_id if mailbox is not None else None
    if active_event_id is not None:
        active = event_index.get(active_event_id)
    if active is None:
        active = next((event for event in events if event['status'] == InboundEventStatus.DELIVERING.value), None)
    last_started = mailbox.last_inbound_started_at if mailbox is not None else None
    last_finished = mailbox.last_inbound_finished_at if mailbox is not None else None
    for event in events:
        started_at = event.get('started_at')
        finished_at = event.get('finished_at')
        if started_at and (last_started is None or started_at > last_started):
            last_started = started_at
        if finished_at and (last_finished is None or finished_at > last_finished):
            last_finished = finished_at
    queue_depth = len(events)
    pending_reply_count = sum(1 for event in events if event['event_type'] == 'task_reply')
    if mailbox is not None:
        mailbox_state = mailbox.mailbox_state.value
        lease_version = mailbox.lease_version
        mailbox_id = mailbox.mailbox_id
    else:
        mailbox_state = derive_mailbox_state(active is not None, queue_depth)
        lease_version = 0
        mailbox_id = f'mbx_{normalized}'
    return {
        'agent_name': normalized,
        'mailbox_id': mailbox_id,
        'mailbox_state': mailbox_state,
        'lease_version': lease_version,
        'queue_depth': queue_depth,
        'pending_reply_count': pending_reply_count,
        'active_inbound_event_id': active['inbound_event_id'] if active is not None else None,
        'active': active,
        'last_inbound_started_at': last_started,
        'last_inbound_finished_at': last_finished,
        'queued_events': events,
    }


def inbox(service, agent_name: str) -> dict[str, object]:
    normalized = _require_mailbox_target(service, agent_name)

    mailbox_payload = agent_queue(service, normalized)
    records = pending_event_records(service, normalized)
    items = [inbox_item_summary(service, record, position=index) for index, record in enumerate(records, start=1)]
    head = items[0] if items else None
    return {
        'target': normalized,
        'agent': mailbox_payload,
        'item_count': len(items),
        'head': head,
        'items': items,
    }


def ack_reply(service, agent_name: str, inbound_event_id: str | None = None) -> dict[str, object]:
    normalized = _require_mailbox_target(service, agent_name)

    head = service._mailbox_kernel.head_pending_event(normalized)
    if head is None:
        raise ValueError(f'inbox is empty for agent: {normalized}')

    requested_event_id = str(inbound_event_id or '').strip() or head.inbound_event_id
    if head.inbound_event_id != requested_event_id:
        raise ValueError(f'ack requires head event: {head.inbound_event_id}')
    if head.event_type is not InboundEventType.TASK_REPLY:
        raise ValueError(f'ack only supports task_reply head events; found: {head.event_type.value}')
    delivery_job_id = delivery_job_id_from_payload(head.payload_ref)
    if delivery_job_id:
        raise ValueError(f'ack is not allowed after automatic reply delivery has been scheduled: {delivery_job_id}')

    reply = reply_for_event(service, head)
    if reply is None:
        raise ValueError(f'reply record missing for inbound event: {head.inbound_event_id}')
    attempt = service._attempt_store.get_latest(head.attempt_id) if head.attempt_id else None

    timestamp = service._clock()
    consumed = service._mailbox_kernel.ack_reply(
        normalized,
        head.inbound_event_id,
        started_at=timestamp,
        finished_at=timestamp,
    )
    if consumed is None:
        raise RuntimeError(f'failed to ack reply event: {head.inbound_event_id}')

    mailbox_payload = agent_queue(service, normalized)
    next_head = service._mailbox_kernel.head_pending_event(normalized)
    return {
        'target': normalized,
        'agent_name': normalized,
        'acknowledged_inbound_event_id': consumed.inbound_event_id,
        'message_id': consumed.message_id,
        'attempt_id': consumed.attempt_id,
        'job_id': attempt.job_id if attempt is not None else None,
        'reply_id': reply.reply_id,
        'reply_from_agent': reply.agent_name,
        'reply_terminal_status': reply.terminal_status.value,
        'reply_finished_at': reply.finished_at,
        'reply_notice': reply_notice(reply),
        'reply_notice_kind': reply_notice_kind(reply),
        'reply_last_progress_at': reply_last_progress_at(reply),
        'reply_heartbeat_silence_seconds': reply_heartbeat_silence_seconds(reply),
        'next_inbound_event_id': next_head.inbound_event_id if next_head is not None else None,
        'next_event_type': next_head.event_type.value if next_head is not None else None,
        'mailbox': mailbox_payload,
        'reply': reply.reply,
    }


def pending_event_records(service, agent_name: str) -> list:
    latest_by_id: dict[str, object] = {}
    order: list[str] = []
    for record in service._inbound_store.list_agent(agent_name):
        if record.inbound_event_id not in latest_by_id:
            order.append(record.inbound_event_id)
        latest_by_id[record.inbound_event_id] = record
    return [
        latest_by_id[inbound_event_id]
        for inbound_event_id in order
        if latest_by_id[inbound_event_id].status not in _TERMINAL_EVENT_STATES
    ]


def pending_events(service, agent_name: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for position, record in enumerate(pending_event_records(service, agent_name), start=1):
        attempt = service._attempt_store.get_latest(record.attempt_id) if record.attempt_id else None
        message = service._message_store.get_latest(record.message_id)
        replies = service._reply_store.list_message(record.message_id)
        events.append(
            {
                'position': position,
                'inbound_event_id': record.inbound_event_id,
                'event_type': record.event_type.value,
                'status': record.status.value,
                'priority': record.priority,
                'message_id': record.message_id,
                'message_state': message.message_state.value if message is not None else None,
                'attempt_id': record.attempt_id,
                'attempt_state': attempt.attempt_state.value if attempt is not None else None,
                'job_id': attempt.job_id if attempt is not None else None,
                'reply_count': len(replies),
                'created_at': record.created_at,
                'started_at': record.started_at,
                'finished_at': record.finished_at,
            }
        )
    return events


def derive_mailbox_state(has_active: bool, queue_depth: int) -> str:
    if has_active:
        return MailboxState.DELIVERING.value
    if queue_depth > 0:
        return MailboxState.BLOCKED.value
    return MailboxState.IDLE.value


def reply_for_event(service, event):
    if event.event_type is not InboundEventType.TASK_REPLY:
        return None
    reply_id = reply_id_from_payload(event.payload_ref)
    if not reply_id:
        return None
    return service._reply_store.get_latest(reply_id)


def inbox_item_summary(service, event, *, position: int) -> dict[str, object]:
    attempt = service._attempt_store.get_latest(event.attempt_id) if event.attempt_id else None
    message = service._message_store.get_latest(event.message_id)
    reply = reply_for_event(service, event)
    item = {
        'position': position,
        'inbound_event_id': event.inbound_event_id,
        'event_type': event.event_type.value,
        'status': event.status.value,
        'priority': event.priority,
        'message_id': event.message_id,
        'message_state': message.message_state.value if message is not None else None,
        'attempt_id': event.attempt_id,
        'attempt_state': attempt.attempt_state.value if attempt is not None else None,
        'job_id': attempt.job_id if attempt is not None else None,
        'source_actor': reply.agent_name if reply is not None else (message.from_actor if message is not None else None),
        'created_at': event.created_at,
        'started_at': event.started_at,
        'finished_at': event.finished_at,
    }
    if reply is not None:
        item.update(
            {
                'reply_id': reply.reply_id,
                'reply_terminal_status': reply.terminal_status.value,
                'reply_finished_at': reply.finished_at,
                'reply_preview': _preview_text(reply.reply),
                'reply_notice': reply_notice(reply),
                'reply_notice_kind': reply_notice_kind(reply),
                'reply_last_progress_at': reply_last_progress_at(reply),
                'reply_heartbeat_silence_seconds': reply_heartbeat_silence_seconds(reply),
            }
        )
        if position == 1:
            item['reply'] = reply.reply
    return item


def _preview_text(value: str, *, limit: int = 120) -> str:
    text = str(value or '').replace('\r', '').replace('\n', '\\n').strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + '...'


def _require_mailbox_target(service, agent_name: str) -> str:
    normalized = normalize_mailbox_target(agent_name, known_targets=service._known_mailboxes)
    if normalized is None:
        raise ValueError(f'unknown mailbox target: {str(agent_name or "").strip().lower()}')
    return normalized


def _summary_targets(service) -> tuple[str, ...]:
    targets = set(getattr(service._config, 'agents', {}).keys())
    if _mailbox_has_activity(service, COMMAND_MAILBOX_ACTOR):
        targets.add(COMMAND_MAILBOX_ACTOR)
    return tuple(sorted(targets))


def _mailbox_has_activity(service, agent_name: str) -> bool:
    mailbox = service._mailbox_store.load(agent_name)
    if mailbox is not None and (mailbox.queue_depth > 0 or mailbox.pending_reply_count > 0 or mailbox.active_inbound_event_id):
        return True
    return any(True for _ in service._inbound_store.list_agent(agent_name))


__all__ = [
    'ack_reply',
    'agent_queue',
    'derive_mailbox_state',
    'inbox',
    'pending_event_records',
    'pending_events',
    'queue_summary',
    'reply_for_event',
]
