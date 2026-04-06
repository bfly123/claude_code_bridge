from __future__ import annotations

from dataclasses import replace

from ..mailbox import refresh_mailbox
from ..queries import head_pending_event, peek_next
from .leasing import next_lease_version


def claim(service, agent_name: str, inbound_event_id: str, *, started_at: str | None = None):
    normalized = service._normalize_agent_name(agent_name)
    timestamp = started_at or service._clock()
    current = service._inbound_store.get_latest(normalized, inbound_event_id)
    if current is None or current.status in service._terminal_event_states:
        return _refresh_none(service, normalized, timestamp)

    lease = service._lease_store.load(normalized)
    if lease is not None and lease.lease_state is service._lease_state_acquired and lease.inbound_event_id != inbound_event_id:
        return _refresh_none(service, normalized, timestamp)
    if current.status is service._status_delivering:
        refresh_mailbox(service, normalized, updated_at=timestamp)
        return current
    if current.status not in service._claimable_event_states:
        return _refresh_none(service, normalized, timestamp)
    head = head_pending_event(service, normalized)
    if head is None or head.inbound_event_id != inbound_event_id:
        return _refresh_none(service, normalized, timestamp)

    updated = replace(
        current,
        status=service._status_delivering,
        started_at=current.started_at or timestamp,
        finished_at=None,
    )
    service._inbound_store.append(updated)
    service._lease_store.save(
        service._delivery_lease_cls(
            agent_name=normalized,
            inbound_event_id=inbound_event_id,
            lease_version=next_lease_version(service, normalized),
            acquired_at=timestamp,
            last_progress_at=timestamp,
            expires_at=None,
            lease_state=service._lease_state_acquired,
        )
    )
    refresh_mailbox(service, normalized, updated_at=timestamp)
    return updated


def claim_next(service, agent_name: str, *, event_type=None, started_at: str | None = None):
    next_event = peek_next(service, agent_name, event_type=event_type)
    if next_event is None:
        refresh_mailbox(service, agent_name, updated_at=started_at or service._clock())
        return None
    return claim(service, agent_name, next_event.inbound_event_id, started_at=started_at)


def _refresh_none(service, agent_name: str, timestamp: str):
    refresh_mailbox(service, agent_name, updated_at=timestamp)
    return None


__all__ = ['claim', 'claim_next']
