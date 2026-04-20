from __future__ import annotations

from message_bureau.reply_payloads import delivery_job_id_from_payload

from ..records import get_job
from .common import head_reply_event, is_reply_delivery_job, reply_delivery_inbound_event_id
from .constants import PENDING_JOB_STATUSES


def claimable_reply_delivery_job_ids(dispatcher, agent_name: str) -> tuple[str, ...]:
    head = head_reply_event(dispatcher, agent_name)
    if head is None:
        return ()
    job_id = delivery_job_id_from_payload(head.payload_ref)
    if not job_id:
        return ()
    current = get_job(dispatcher, job_id)
    if current is None:
        return ()
    if current.status not in PENDING_JOB_STATUSES:
        return ()
    return (job_id,)


def claim_reply_delivery_start(dispatcher, job, *, started_at: str) -> bool:
    if not is_reply_delivery_job(job):
        return True
    inbound_event_id = reply_delivery_inbound_event_id(job)
    if not inbound_event_id:
        return False
    head = head_reply_event(dispatcher, job.agent_name)
    if head is None or head.inbound_event_id != inbound_event_id:
        return False
    claimed = dispatcher._message_bureau_control._mailbox_kernel.claim(
        job.agent_name,
        inbound_event_id,
        started_at=started_at,
    )
    return claimed is not None


__all__ = ['claim_reply_delivery_start', 'claimable_reply_delivery_job_ids', 'is_reply_delivery_job']
