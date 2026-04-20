from __future__ import annotations

from dataclasses import replace

from ..mailbox import refresh_mailbox
from ..queries import head_pending_event
from .claiming import claim


def ack_reply(
    service,
    agent_name: str,
    inbound_event_id: str,
    *,
    started_at: str | None = None,
    finished_at: str | None = None,
):
    normalized = service._normalize_agent_name(agent_name)
    head = head_pending_event(service, normalized)
    timestamp = _ack_timestamp(service, started_at=started_at, finished_at=finished_at)
    if not _head_matches_reply(service, head, inbound_event_id=inbound_event_id):
        return _refresh_and_return(service, normalized, timestamp=timestamp)

    current = service._inbound_store.get_latest(normalized, inbound_event_id)
    if current is None or current.status in service._terminal_event_states:
        return _refresh_and_return(service, normalized, timestamp=timestamp, value=current)

    if current.status is service._status_delivering:
        return mark_terminal(
            service,
            normalized,
            inbound_event_id,
            status=service._status_consumed,
            finished_at=finished_at or timestamp,
        )

    claimed = claim(service, normalized, inbound_event_id, started_at=started_at or timestamp)
    if claimed is None:
        return _refresh_and_return(service, normalized, timestamp=timestamp)
    return mark_terminal(
        service,
        normalized,
        inbound_event_id,
        status=service._status_consumed,
        finished_at=finished_at or timestamp,
    )


def mark_terminal(
    service,
    agent_name: str,
    inbound_event_id: str,
    *,
    status,
    finished_at: str | None = None,
):
    normalized = service._normalize_agent_name(agent_name)
    timestamp = finished_at or service._clock()
    current = service._inbound_store.get_latest(normalized, inbound_event_id)
    if current is None:
        return _refresh_and_return(service, normalized, timestamp=timestamp)
    if current.status in service._terminal_event_states:
        return _refresh_and_return(service, normalized, timestamp=timestamp, value=current)

    updated = replace(current, status=status, finished_at=timestamp)
    service._inbound_store.append(updated)
    _release_matching_lease(service, normalized, inbound_event_id=inbound_event_id)
    refresh_mailbox(service, normalized, updated_at=timestamp)
    return updated


def _ack_timestamp(service, *, started_at: str | None, finished_at: str | None) -> str:
    return finished_at or started_at or service._clock()


def _head_matches_reply(service, head, *, inbound_event_id: str) -> bool:
    if head is None:
        return False
    if head.inbound_event_id != inbound_event_id:
        return False
    return head.event_type is service._reply_event_type


def _refresh_and_return(service, agent_name: str, *, timestamp: str, value=None):
    refresh_mailbox(service, agent_name, updated_at=timestamp)
    return value


def _release_matching_lease(service, agent_name: str, *, inbound_event_id: str) -> None:
    lease = service._lease_store.load(agent_name)
    if lease is None:
        return
    if lease.lease_state is not service._lease_state_acquired:
        return
    if lease.inbound_event_id != inbound_event_id:
        return
    service._lease_store.remove(agent_name)


__all__ = ['ack_reply', 'mark_terminal']
