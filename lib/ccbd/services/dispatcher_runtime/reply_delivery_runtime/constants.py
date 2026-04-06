from __future__ import annotations

from ccbd.api_models import JobStatus


REPLY_DELIVERY_MESSAGE_TYPE = 'reply_delivery'
REPLY_DELIVERY_PROVIDER_OPTION = 'reply_delivery'
REPLY_DELIVERY_INBOUND_EVENT_OPTION = 'reply_delivery_inbound_event_id'
REPLY_DELIVERY_REPLY_ID_OPTION = 'reply_delivery_reply_id'
PENDING_JOB_STATUSES = frozenset({JobStatus.ACCEPTED, JobStatus.QUEUED})
TERMINAL_JOB_STATUSES = frozenset(
    {
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.INCOMPLETE,
        JobStatus.CANCELLED,
    }
)


__all__ = [
    'PENDING_JOB_STATUSES',
    'REPLY_DELIVERY_INBOUND_EVENT_OPTION',
    'REPLY_DELIVERY_MESSAGE_TYPE',
    'REPLY_DELIVERY_PROVIDER_OPTION',
    'REPLY_DELIVERY_REPLY_ID_OPTION',
    'TERMINAL_JOB_STATUSES',
]
