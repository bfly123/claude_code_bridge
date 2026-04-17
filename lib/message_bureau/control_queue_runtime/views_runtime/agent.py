from __future__ import annotations

from mailbox_kernel import InboundEventStatus

from ..common import derive_mailbox_state, require_mailbox_target
from ..events import pending_events


def agent_queue(service, agent_name: str) -> dict[str, object]:
    normalized = require_mailbox_target(service, agent_name)
    mailbox = service._mailbox_store.load(normalized)
    events = pending_events(service, normalized)
    active = _active_event(events, mailbox)
    last_started, last_finished = _last_event_timestamps(events, mailbox)
    queue_depth = len(events)
    pending_reply_count = sum(1 for event in events if event['event_type'] == 'task_reply')
    mailbox_id, mailbox_state, lease_version = _mailbox_facts(normalized, mailbox, active=active, queue_depth=queue_depth)
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


def _active_event(events: tuple[dict, ...], mailbox) -> dict | None:
    event_index = {event['inbound_event_id']: event for event in events}
    active_event_id = mailbox.active_inbound_event_id if mailbox is not None else None
    if active_event_id is not None:
        active = event_index.get(active_event_id)
        if active is not None:
            return active
    return next((event for event in events if event['status'] == InboundEventStatus.DELIVERING.value), None)


def _last_event_timestamps(events: tuple[dict, ...], mailbox) -> tuple[str | None, str | None]:
    last_started = mailbox.last_inbound_started_at if mailbox is not None and events else None
    last_finished = mailbox.last_inbound_finished_at if mailbox is not None and events else None
    for event in events:
        started_at = event.get('started_at')
        finished_at = event.get('finished_at')
        if started_at and (last_started is None or started_at > last_started):
            last_started = started_at
        if finished_at and (last_finished is None or finished_at > last_finished):
            last_finished = finished_at
    return last_started, last_finished


def _mailbox_facts(normalized: str, mailbox, *, active: dict | None, queue_depth: int) -> tuple[str, str, int]:
    if mailbox is not None:
        return mailbox.mailbox_id, derive_mailbox_state(active is not None, queue_depth), mailbox.lease_version
    return f'mbx_{normalized}', derive_mailbox_state(active is not None, queue_depth), 0


__all__ = ['agent_queue']
