from __future__ import annotations

from mailbox_kernel import InboundEventStatus
from message_bureau.reply_payloads import delivery_job_id_from_payload

from ..records import get_job
from .common import head_reply_event
from .constants import PENDING_JOB_STATUSES, TERMINAL_JOB_STATUSES
from .head import rewrite_reply_head


def reload_reply_head(dispatcher, agent_name: str):
    return head_reply_event(dispatcher, agent_name)


def reset_stale_reply_head(dispatcher, head, *, reply_id: str, agent_name: str):
    rewrite_reply_head(
        dispatcher,
        head,
        reply_id=reply_id,
        delivery_job_id=None,
        status=InboundEventStatus.QUEUED,
        updated_at=dispatcher._clock(),
        clear_progress=True,
    )
    return reload_reply_head(dispatcher, agent_name)


def resolve_existing_delivery_job(dispatcher, agent_name: str, head, *, reply_id: str):
    delivery_job_id = delivery_job_id_from_payload(head.payload_ref)
    if not delivery_job_id:
        return head
    current = get_job(dispatcher, delivery_job_id)
    if current is None:
        return reset_stale_reply_head(
            dispatcher,
            head,
            reply_id=reply_id,
            agent_name=agent_name,
        )
    if current.status in PENDING_JOB_STATUSES or current.status.value == 'running':
        return False
    if current.status.value == 'completed':
        from .terminal import resolve_reply_delivery_terminal

        resolve_reply_delivery_terminal(dispatcher, current, finished_at=current.updated_at)
        return None
    if current.status in TERMINAL_JOB_STATUSES:
        return reset_stale_reply_head(
            dispatcher,
            head,
            reply_id=reply_id,
            agent_name=agent_name,
        )
    return head


__all__ = [
    'resolve_existing_delivery_job',
]
