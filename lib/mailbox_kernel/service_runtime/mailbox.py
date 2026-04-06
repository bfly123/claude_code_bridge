from __future__ import annotations

from mailbox_runtime.targets import normalize_mailbox_owner_name

from .queries import latest_events, pending_events


def refresh_mailbox(service, agent_name: str, *, updated_at: str | None = None):
    normalized = normalize_mailbox_owner_name(agent_name)
    timestamp = updated_at or service._clock()
    prior = service._mailbox_store.load(normalized)
    lease = service._lease_store.load(normalized)
    events = pending_events(service, normalized)
    queue_depth = len(events)
    pending_reply_count = sum(1 for event in events if event.event_type is service._reply_event_type)
    mailbox_state, active_inbound_event_id, lease_version = _mailbox_facts(
        service,
        prior=prior,
        lease=lease,
        queue_depth=queue_depth,
    )
    last_started, last_finished = _latest_activity(
        service,
        normalized,
        prior=prior,
    )

    record = service._mailbox_record_cls(
        mailbox_id=prior.mailbox_id if prior is not None else f'mbx_{normalized}',
        agent_name=normalized,
        active_inbound_event_id=active_inbound_event_id,
        queue_depth=queue_depth,
        pending_reply_count=pending_reply_count,
        last_inbound_started_at=last_started,
        last_inbound_finished_at=last_finished,
        mailbox_state=mailbox_state,
        lease_version=lease_version,
        updated_at=timestamp,
    )
    service._mailbox_store.save(record)
    return record


def _mailbox_facts(service, *, prior, lease, queue_depth: int):
    if lease is not None and lease.lease_state is service._lease_state_acquired:
        return (
            service._mailbox_state_delivering,
            lease.inbound_event_id,
            lease.lease_version,
        )
    if queue_depth > 0:
        return (
            service._mailbox_state_blocked,
            None,
            _prior_lease_version(prior),
        )
    return (
        service._mailbox_state_idle,
        None,
        _prior_lease_version(prior),
    )


def _prior_lease_version(prior) -> int:
    return prior.lease_version if prior is not None else 0


def _latest_activity(service, normalized: str, *, prior):
    last_started = prior.last_inbound_started_at if prior is not None else None
    last_finished = prior.last_inbound_finished_at if prior is not None else None
    for event in latest_events(service, normalized):
        last_started = _latest_timestamp(last_started, event.started_at)
        last_finished = _latest_timestamp(last_finished, event.finished_at)
    return last_started, last_finished


def _latest_timestamp(current: str | None, candidate: str | None) -> str | None:
    if candidate and (current is None or candidate > current):
        return candidate
    return current


__all__ = ['refresh_mailbox']
