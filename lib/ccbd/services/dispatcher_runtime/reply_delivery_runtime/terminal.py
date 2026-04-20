from __future__ import annotations

from mailbox_kernel import InboundEventStatus

from ..records import append_event
from .common import is_reply_delivery_job, reply_delivery_inbound_event_id, reply_delivery_reply_id
from .head import rewrite_reply_head


def resolve_reply_delivery_terminal(dispatcher, job, *, finished_at: str) -> None:
    if not is_reply_delivery_job(job):
        return

    inbound_event_id = reply_delivery_inbound_event_id(job)
    reply_id = reply_delivery_reply_id(job)
    if not inbound_event_id or not reply_id:
        return

    control = dispatcher._message_bureau_control
    current = control._inbound_store.get_latest(job.agent_name, inbound_event_id)
    if current is None:
        return

    if job.status.value == 'completed':
        control._mailbox_kernel.consume(job.agent_name, inbound_event_id, finished_at=finished_at)
        append_event(
            dispatcher,
            job,
            'reply_delivery_consumed',
            {
                'inbound_event_id': inbound_event_id,
                'reply_id': reply_id,
            },
            timestamp=finished_at,
        )
        return

    rewrite_reply_head(
        dispatcher,
        current,
        reply_id=reply_id,
        delivery_job_id=None,
        status=InboundEventStatus.QUEUED,
        updated_at=finished_at,
        clear_progress=True,
    )
    append_event(
        dispatcher,
        job,
        'reply_delivery_requeued',
        {
            'inbound_event_id': inbound_event_id,
            'reply_id': reply_id,
            'terminal_status': job.status.value,
        },
        timestamp=finished_at,
    )


__all__ = ['resolve_reply_delivery_terminal']
