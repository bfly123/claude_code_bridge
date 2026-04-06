from __future__ import annotations

from mailbox_kernel import InboundEventRecord, InboundEventStatus, InboundEventType
from message_bureau.reply_payloads import compose_reply_payload


def rewrite_reply_head(
    dispatcher,
    current,
    *,
    reply_id: str,
    delivery_job_id: str | None,
    status: InboundEventStatus,
    updated_at: str,
    clear_progress: bool,
) -> None:
    control = dispatcher._message_bureau_control
    updated = InboundEventRecord(
        inbound_event_id=current.inbound_event_id,
        agent_name=current.agent_name,
        event_type=InboundEventType.TASK_REPLY,
        message_id=current.message_id,
        attempt_id=current.attempt_id,
        payload_ref=compose_reply_payload(reply_id, delivery_job_id=delivery_job_id),
        priority=current.priority,
        status=status,
        created_at=current.created_at,
        started_at=None if clear_progress else current.started_at,
        finished_at=None if clear_progress else current.finished_at,
    )
    control._inbound_store.append(updated)
    lease = control._lease_store.load(current.agent_name)
    if lease is not None and lease.inbound_event_id == current.inbound_event_id:
        control._lease_store.remove(current.agent_name)
    control._mailbox_kernel.refresh_mailbox(current.agent_name, updated_at=updated_at)


__all__ = ['rewrite_reply_head']
