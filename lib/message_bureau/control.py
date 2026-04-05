from __future__ import annotations

from datetime import datetime, timezone

from jobs.store import JobStore, SubmissionStore
from mailbox_targets import known_mailbox_targets
from mailbox_kernel import (
    DeliveryLeaseStore,
    InboundEventStore,
    MailboxKernelService,
    MailboxStore,
)
from storage.paths import PathLayout

from .control_queue import ack_reply as control_ack_reply
from .control_queue import agent_queue as control_agent_queue
from .control_queue import inbox as control_inbox
from .control_queue import queue_summary as control_queue_summary
from .control_trace import trace as control_trace
from .store import AttemptStore, MessageStore, ReplyStore


class MessageBureauControlService:
    def __init__(
        self,
        layout: PathLayout,
        config,
        *,
        mailbox_store: MailboxStore | None = None,
        inbound_store: InboundEventStore | None = None,
        lease_store: DeliveryLeaseStore | None = None,
        message_store: MessageStore | None = None,
        attempt_store: AttemptStore | None = None,
        reply_store: ReplyStore | None = None,
        job_store: JobStore | None = None,
        submission_store: SubmissionStore | None = None,
        mailbox_kernel: MailboxKernelService | None = None,
        clock=None,
    ) -> None:
        self._layout = layout
        self._config = config
        self._known_mailboxes = known_mailbox_targets(config)
        self._clock = clock or _utc_now
        self._mailbox_store = mailbox_store or MailboxStore(layout)
        self._inbound_store = inbound_store or InboundEventStore(layout)
        self._lease_store = lease_store or DeliveryLeaseStore(layout)
        self._message_store = message_store or MessageStore(layout)
        self._attempt_store = attempt_store or AttemptStore(layout)
        self._reply_store = reply_store or ReplyStore(layout)
        self._job_store = job_store or JobStore(layout)
        self._submission_store = submission_store or SubmissionStore(layout)
        self._mailbox_kernel = mailbox_kernel or MailboxKernelService(
            layout,
            clock=self._clock,
            mailbox_store=self._mailbox_store,
            inbound_store=self._inbound_store,
            lease_store=self._lease_store,
        )

    def queue_summary(self, target: str = 'all') -> dict[str, object]:
        return control_queue_summary(self, target)

    def agent_queue(self, agent_name: str) -> dict[str, object]:
        return control_agent_queue(self, agent_name)

    def trace(self, target: str) -> dict[str, object]:
        return control_trace(self, target)

    def inbox(self, agent_name: str) -> dict[str, object]:
        return control_inbox(self, agent_name)

    def ack_reply(self, agent_name: str, inbound_event_id: str | None = None) -> dict[str, object]:
        return control_ack_reply(self, agent_name, inbound_event_id=inbound_event_id)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


__all__ = ['MessageBureauControlService']
