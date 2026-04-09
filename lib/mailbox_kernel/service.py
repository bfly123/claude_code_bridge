from __future__ import annotations

from mailbox_runtime.targets import normalize_mailbox_owner_name
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
from .service_state import MailboxKernelRuntimeState, MailboxKernelStateMixin
from .store import DeliveryLeaseStore, InboundEventStore, MailboxStore
from .service_runtime import ack_reply, claim, claim_next, head_pending_event, latest_events, mark_terminal, peek_next, pending_events, refresh_mailbox

_TERMINAL_EVENT_STATES = frozenset(
    {
        InboundEventStatus.CONSUMED,
        InboundEventStatus.SUPERSEDED,
        InboundEventStatus.ABANDONED,
    }
)
_CLAIMABLE_EVENT_STATES = frozenset({InboundEventStatus.CREATED, InboundEventStatus.QUEUED})


class MailboxKernelService(MailboxKernelStateMixin):
    def __init__(
        self,
        layout: PathLayout,
        *,
        clock,
        mailbox_store: MailboxStore | None = None,
        inbound_store: InboundEventStore | None = None,
        lease_store: DeliveryLeaseStore | None = None,
    ) -> None:
        self._runtime_state = MailboxKernelRuntimeState(
            layout=layout,
            clock=clock,
            mailbox_store=mailbox_store or MailboxStore(layout),
            inbound_store=inbound_store or InboundEventStore(layout),
            lease_store=lease_store or DeliveryLeaseStore(layout),
            normalize_agent_name=normalize_mailbox_owner_name,
            terminal_event_states=_TERMINAL_EVENT_STATES,
            claimable_event_states=_CLAIMABLE_EVENT_STATES,
            mailbox_record_cls=MailboxRecord,
            delivery_lease_cls=DeliveryLease,
            reply_event_type=InboundEventType.TASK_REPLY,
            lease_state_acquired=LeaseState.ACQUIRED,
            mailbox_state_delivering=MailboxState.DELIVERING,
            mailbox_state_blocked=MailboxState.BLOCKED,
            mailbox_state_idle=MailboxState.IDLE,
            status_delivering=InboundEventStatus.DELIVERING,
            status_consumed=InboundEventStatus.CONSUMED,
        )

    def latest_events(self, agent_name: str) -> tuple[InboundEventRecord, ...]:
        return latest_events(self, agent_name)

    def pending_events(
        self,
        agent_name: str,
        *,
        event_type: InboundEventType | None = None,
    ) -> tuple[InboundEventRecord, ...]:
        return pending_events(self, agent_name, event_type=event_type)

    def head_pending_event(self, agent_name: str) -> InboundEventRecord | None:
        return head_pending_event(self, agent_name)

    def peek_next(
        self,
        agent_name: str,
        *,
        event_type: InboundEventType | None = None,
    ) -> InboundEventRecord | None:
        return peek_next(self, agent_name, event_type=event_type)

    def claim(
        self,
        agent_name: str,
        inbound_event_id: str,
        *,
        started_at: str | None = None,
    ) -> InboundEventRecord | None:
        return claim(self, agent_name, inbound_event_id, started_at=started_at)

    def claim_next(
        self,
        agent_name: str,
        *,
        event_type: InboundEventType | None = None,
        started_at: str | None = None,
    ) -> InboundEventRecord | None:
        return claim_next(self, agent_name, event_type=event_type, started_at=started_at)

    def ack_reply(
        self,
        agent_name: str,
        inbound_event_id: str,
        *,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> InboundEventRecord | None:
        return ack_reply(
            self,
            agent_name,
            inbound_event_id,
            started_at=started_at,
            finished_at=finished_at,
        )

    def consume(
        self,
        agent_name: str,
        inbound_event_id: str,
        *,
        finished_at: str | None = None,
    ) -> InboundEventRecord | None:
        return mark_terminal(self, agent_name, inbound_event_id, status=InboundEventStatus.CONSUMED, finished_at=finished_at)

    def abandon(
        self,
        agent_name: str,
        inbound_event_id: str,
        *,
        finished_at: str | None = None,
    ) -> InboundEventRecord | None:
        return mark_terminal(self, agent_name, inbound_event_id, status=InboundEventStatus.ABANDONED, finished_at=finished_at)

    def supersede(
        self,
        agent_name: str,
        inbound_event_id: str,
        *,
        finished_at: str | None = None,
    ) -> InboundEventRecord | None:
        return mark_terminal(self, agent_name, inbound_event_id, status=InboundEventStatus.SUPERSEDED, finished_at=finished_at)

    def refresh_mailbox(self, agent_name: str, *, updated_at: str | None = None) -> MailboxRecord:
        return refresh_mailbox(self, agent_name, updated_at=updated_at)


__all__ = ['MailboxKernelService']
