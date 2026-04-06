from __future__ import annotations

from ccbd.api_models import JobRecord, MessageEnvelope
from completion.models import CompletionDecision
from mailbox_runtime.targets import known_mailbox_targets
from mailbox_kernel import (
    DeliveryLeaseStore,
    InboundEventStore,
    MailboxKernelService,
    MailboxStore,
)
from storage.paths import PathLayout

from .facade_recording import (
    claimable_request_job_ids as _claimable_request_job_ids_impl,
    mark_attempt_started as _mark_attempt_started_impl,
    record_notice as _record_notice_impl,
    record_attempt_terminal as _record_attempt_terminal_impl,
    record_reply as _record_reply_impl,
    record_retry_attempt as _record_retry_attempt_impl,
    record_submission as _record_submission_impl,
    record_terminal as _record_terminal_impl,
)
from .store import AttemptStore, MessageStore, ReplyStore


class MessageBureauFacade:
    def __init__(
        self,
        layout: PathLayout,
        *,
        config=None,
        clock,
        message_store: MessageStore | None = None,
        attempt_store: AttemptStore | None = None,
        reply_store: ReplyStore | None = None,
        mailbox_store: MailboxStore | None = None,
        inbound_store: InboundEventStore | None = None,
        lease_store: DeliveryLeaseStore | None = None,
        mailbox_kernel: MailboxKernelService | None = None,
    ) -> None:
        self._layout = layout
        self._clock = clock
        self._known_agents = frozenset(getattr(config, 'agents', {}).keys())
        self._known_mailboxes = known_mailbox_targets(config)
        self._message_store = message_store or MessageStore(layout)
        self._attempt_store = attempt_store or AttemptStore(layout)
        self._reply_store = reply_store or ReplyStore(layout)
        self._mailbox_store = mailbox_store or MailboxStore(layout)
        self._inbound_store = inbound_store or InboundEventStore(layout)
        self._lease_store = lease_store or DeliveryLeaseStore(layout)
        self._mailbox_kernel = mailbox_kernel or MailboxKernelService(
            layout,
            clock=clock,
            mailbox_store=self._mailbox_store,
            inbound_store=self._inbound_store,
            lease_store=self._lease_store,
        )

    def record_submission(
        self,
        request: MessageEnvelope,
        jobs: tuple[JobRecord, ...],
        *,
        submission_id: str | None,
        accepted_at: str,
        origin_message_id: str | None = None,
    ) -> str | None:
        return _record_submission_impl(
            self,
            request,
            jobs,
            submission_id=submission_id,
            accepted_at=accepted_at,
            origin_message_id=origin_message_id,
        )

    def claimable_request_job_ids(self, agent_name: str) -> tuple[str, ...]:
        return _claimable_request_job_ids_impl(self, agent_name)

    def mark_attempt_started(self, job: JobRecord, *, started_at: str) -> None:
        _mark_attempt_started_impl(self, job, started_at=started_at)

    def record_attempt_terminal(self, job: JobRecord, decision: CompletionDecision, *, finished_at: str) -> None:
        _record_attempt_terminal_impl(self, job, decision, finished_at=finished_at)

    def record_reply(
        self,
        job: JobRecord,
        decision: CompletionDecision,
        *,
        finished_at: str,
        deliver_to_caller: bool = True,
    ) -> str | None:
        return _record_reply_impl(
            self,
            job,
            decision,
            finished_at=finished_at,
            deliver_to_caller=deliver_to_caller,
        )

    def record_notice(
        self,
        job: JobRecord,
        *,
        reply: str,
        diagnostics: dict[str, object] | None,
        finished_at: str,
        deliver_to_actor: str | None = None,
    ) -> str | None:
        return _record_notice_impl(
            self,
            job,
            reply=reply,
            diagnostics=diagnostics,
            finished_at=finished_at,
            deliver_to_actor=deliver_to_actor,
        )

    def record_terminal(
        self,
        job: JobRecord,
        decision: CompletionDecision,
        *,
        finished_at: str,
        deliver_to_caller: bool = True,
        record_reply: bool = True,
    ) -> str | None:
        return _record_terminal_impl(
            self,
            job,
            decision,
            finished_at=finished_at,
            deliver_to_caller=deliver_to_caller,
            record_reply_enabled=record_reply,
        )

    def record_retry_attempt(self, message_id: str, job: JobRecord, *, accepted_at: str) -> str:
        return _record_retry_attempt_impl(self, message_id, job, accepted_at=accepted_at)


__all__ = ['MessageBureauFacade']
