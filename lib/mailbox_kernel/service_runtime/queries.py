from __future__ import annotations


def latest_events(service, agent_name: str):
    normalized = service._normalize_agent_name(agent_name)
    latest: dict[str, object] = {}
    order: list[str] = []
    for record in service._inbound_store.list_agent(normalized):
        if record.inbound_event_id not in latest:
            order.append(record.inbound_event_id)
        latest[record.inbound_event_id] = record
    return tuple(latest[event_id] for event_id in order)


def pending_events(service, agent_name: str, *, event_type=None):
    events = []
    for record in latest_events(service, agent_name):
        if record.status in service._terminal_event_states:
            continue
        if event_type is not None and record.event_type is not event_type:
            continue
        events.append(record)
    return tuple(events)


def head_pending_event(service, agent_name: str):
    events = pending_events(service, agent_name)
    if not events:
        return None
    return events[0]


def peek_next(service, agent_name: str, *, event_type=None):
    head = head_pending_event(service, agent_name)
    if head is None:
        return None
    if event_type is not None and head.event_type is not event_type:
        return None
    if head.status not in service._claimable_event_states:
        return None
    return head


__all__ = ['head_pending_event', 'latest_events', 'peek_next', 'pending_events']
