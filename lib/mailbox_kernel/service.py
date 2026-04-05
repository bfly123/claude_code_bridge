from __future__ import annotations

from dataclasses import replace

from mailbox_targets import normalize_mailbox_owner_name
from storage.paths import PathLayout

from .models import (
    DeliveryLease,
    InboundEventRecord,
    InboundEventStatus,
    InboundEventType,
    LeaseState,
    MailboxRecord,
    MailboxState,
)
from .store import DeliveryLeaseStore, InboundEventStore, MailboxStore

_TERMINAL_EVENT_STATES = frozenset(
    {
        InboundEventStatus.CONSUMED,
        InboundEventStatus.SUPERSEDED,
        InboundEventStatus.ABANDONED,
    }
)
_CLAIMABLE_EVENT_STATES = frozenset({InboundEventStatus.CREATED, InboundEventStatus.QUEUED})


class MailboxKernelService:
    def __init__(
        self,
        layout: PathLayout,
        *,
        clock,
        mailbox_store: MailboxStore | None = None,
        inbound_store: InboundEventStore | None = None,
        lease_store: DeliveryLeaseStore | None = None,
    ) -> None:
        self._layout = layout
        self._clock = clock
        self._mailbox_store = mailbox_store or MailboxStore(layout)
        self._inbound_store = inbound_store or InboundEventStore(layout)
        self._lease_store = lease_store or DeliveryLeaseStore(layout)

    def latest_events(self, agent_name: str) -> tuple[InboundEventRecord, ...]:
        normalized = normalize_mailbox_owner_name(agent_name)
        latest: dict[str, InboundEventRecord] = {}
        order: list[str] = []
        for record in self._inbound_store.list_agent(normalized):
            if record.inbound_event_id not in latest:
                order.append(record.inbound_event_id)
            latest[record.inbound_event_id] = record
        return tuple(latest[event_id] for event_id in order)

    def pending_events(
        self,
        agent_name: str,
        *,
        event_type: InboundEventType | None = None,
    ) -> tuple[InboundEventRecord, ...]:
        events = []
        for record in self.latest_events(agent_name):
            if record.status in _TERMINAL_EVENT_STATES:
                continue
            if event_type is not None and record.event_type is not event_type:
                continue
            events.append(record)
        return tuple(events)

    def head_pending_event(self, agent_name: str) -> InboundEventRecord | None:
        events = self.pending_events(agent_name)
        if not events:
            return None
        return events[0]

    def peek_next(
        self,
        agent_name: str,
        *,
        event_type: InboundEventType | None = None,
    ) -> InboundEventRecord | None:
        head = self.head_pending_event(agent_name)
        if head is None:
            return None
        if event_type is not None and head.event_type is not event_type:
            return None
        if head.status not in _CLAIMABLE_EVENT_STATES:
            return None
        return head

    def claim(
        self,
        agent_name: str,
        inbound_event_id: str,
        *,
        started_at: str | None = None,
    ) -> InboundEventRecord | None:
        normalized = normalize_mailbox_owner_name(agent_name)
        timestamp = started_at or self._clock()
        current = self._inbound_store.get_latest(normalized, inbound_event_id)
        if current is None or current.status in _TERMINAL_EVENT_STATES:
            self.refresh_mailbox(normalized, updated_at=timestamp)
            return None

        lease = self._lease_store.load(normalized)
        if lease is not None and lease.lease_state is LeaseState.ACQUIRED and lease.inbound_event_id != inbound_event_id:
            self.refresh_mailbox(normalized, updated_at=timestamp)
            return None
        if current.status is InboundEventStatus.DELIVERING:
            self.refresh_mailbox(normalized, updated_at=timestamp)
            return current
        if current.status not in _CLAIMABLE_EVENT_STATES:
            self.refresh_mailbox(normalized, updated_at=timestamp)
            return None
        head = self.head_pending_event(normalized)
        if head is None or head.inbound_event_id != inbound_event_id:
            self.refresh_mailbox(normalized, updated_at=timestamp)
            return None

        updated = replace(
            current,
            status=InboundEventStatus.DELIVERING,
            started_at=current.started_at or timestamp,
            finished_at=None,
        )
        self._inbound_store.append(updated)
        self._lease_store.save(
            DeliveryLease(
                agent_name=normalized,
                inbound_event_id=inbound_event_id,
                lease_version=self._next_lease_version(normalized),
                acquired_at=timestamp,
                last_progress_at=timestamp,
                expires_at=None,
                lease_state=LeaseState.ACQUIRED,
            )
        )
        self.refresh_mailbox(normalized, updated_at=timestamp)
        return updated

    def claim_next(
        self,
        agent_name: str,
        *,
        event_type: InboundEventType | None = None,
        started_at: str | None = None,
    ) -> InboundEventRecord | None:
        next_event = self.peek_next(agent_name, event_type=event_type)
        if next_event is None:
            self.refresh_mailbox(agent_name, updated_at=started_at or self._clock())
            return None
        return self.claim(agent_name, next_event.inbound_event_id, started_at=started_at)

    def ack_reply(
        self,
        agent_name: str,
        inbound_event_id: str,
        *,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> InboundEventRecord | None:
        normalized = normalize_mailbox_owner_name(agent_name)
        head = self.head_pending_event(normalized)
        timestamp = finished_at or started_at or self._clock()
        if head is None or head.inbound_event_id != inbound_event_id:
            self.refresh_mailbox(normalized, updated_at=timestamp)
            return None
        if head.event_type is not InboundEventType.TASK_REPLY:
            self.refresh_mailbox(normalized, updated_at=timestamp)
            return None

        current = self._inbound_store.get_latest(normalized, inbound_event_id)
        if current is None or current.status in _TERMINAL_EVENT_STATES:
            self.refresh_mailbox(normalized, updated_at=timestamp)
            return current

        if current.status is InboundEventStatus.DELIVERING:
            return self.consume(normalized, inbound_event_id, finished_at=finished_at or timestamp)

        claimed = self.claim(normalized, inbound_event_id, started_at=started_at or timestamp)
        if claimed is None:
            self.refresh_mailbox(normalized, updated_at=timestamp)
            return None
        return self.consume(normalized, inbound_event_id, finished_at=finished_at or timestamp)

    def consume(
        self,
        agent_name: str,
        inbound_event_id: str,
        *,
        finished_at: str | None = None,
    ) -> InboundEventRecord | None:
        return self._mark_terminal(agent_name, inbound_event_id, status=InboundEventStatus.CONSUMED, finished_at=finished_at)

    def abandon(
        self,
        agent_name: str,
        inbound_event_id: str,
        *,
        finished_at: str | None = None,
    ) -> InboundEventRecord | None:
        return self._mark_terminal(agent_name, inbound_event_id, status=InboundEventStatus.ABANDONED, finished_at=finished_at)

    def supersede(
        self,
        agent_name: str,
        inbound_event_id: str,
        *,
        finished_at: str | None = None,
    ) -> InboundEventRecord | None:
        return self._mark_terminal(agent_name, inbound_event_id, status=InboundEventStatus.SUPERSEDED, finished_at=finished_at)

    def refresh_mailbox(self, agent_name: str, *, updated_at: str | None = None) -> MailboxRecord:
        normalized = normalize_mailbox_owner_name(agent_name)
        timestamp = updated_at or self._clock()
        prior = self._mailbox_store.load(normalized)
        lease = self._lease_store.load(normalized)
        events = self.pending_events(normalized)
        queue_depth = len(events)
        pending_reply_count = sum(1 for event in events if event.event_type is InboundEventType.TASK_REPLY)

        if lease is not None and lease.lease_state is LeaseState.ACQUIRED:
            mailbox_state = MailboxState.DELIVERING
            active_inbound_event_id = lease.inbound_event_id
            lease_version = lease.lease_version
        elif queue_depth > 0:
            mailbox_state = MailboxState.BLOCKED
            active_inbound_event_id = None
            lease_version = prior.lease_version if prior is not None else 0
        else:
            mailbox_state = MailboxState.IDLE
            active_inbound_event_id = None
            lease_version = prior.lease_version if prior is not None else 0

        last_started = prior.last_inbound_started_at if prior is not None else None
        last_finished = prior.last_inbound_finished_at if prior is not None else None
        for event in self.latest_events(normalized):
            if event.started_at and (last_started is None or event.started_at > last_started):
                last_started = event.started_at
            if event.finished_at and (last_finished is None or event.finished_at > last_finished):
                last_finished = event.finished_at

        record = MailboxRecord(
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
        self._mailbox_store.save(record)
        return record

    def _mark_terminal(
        self,
        agent_name: str,
        inbound_event_id: str,
        *,
        status: InboundEventStatus,
        finished_at: str | None = None,
    ) -> InboundEventRecord | None:
        normalized = normalize_mailbox_owner_name(agent_name)
        timestamp = finished_at or self._clock()
        current = self._inbound_store.get_latest(normalized, inbound_event_id)
        if current is None:
            self.refresh_mailbox(normalized, updated_at=timestamp)
            return None
        if current.status in _TERMINAL_EVENT_STATES:
            self.refresh_mailbox(normalized, updated_at=timestamp)
            return current

        updated = replace(current, status=status, finished_at=timestamp)
        self._inbound_store.append(updated)
        lease = self._lease_store.load(normalized)
        if lease is not None and lease.lease_state is LeaseState.ACQUIRED and lease.inbound_event_id == inbound_event_id:
            self._lease_store.remove(normalized)
        self.refresh_mailbox(normalized, updated_at=timestamp)
        return updated

    def _next_lease_version(self, agent_name: str) -> int:
        normalized = normalize_mailbox_owner_name(agent_name)
        lease = self._lease_store.load(normalized)
        if lease is not None:
            return lease.lease_version + 1
        mailbox = self._mailbox_store.load(normalized)
        if mailbox is not None:
            return mailbox.lease_version + 1
        return 1


__all__ = ['MailboxKernelService']
