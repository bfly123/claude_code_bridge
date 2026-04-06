from __future__ import annotations

from ccbd.api_models import JobRecord
from mailbox_kernel import InboundEventType
from message_bureau.reply_payloads import reply_id_from_payload

from .constants import REPLY_DELIVERY_INBOUND_EVENT_OPTION, REPLY_DELIVERY_MESSAGE_TYPE, REPLY_DELIVERY_PROVIDER_OPTION, REPLY_DELIVERY_REPLY_ID_OPTION


def head_reply_event(dispatcher, agent_name: str):
    head = dispatcher._message_bureau_control._mailbox_kernel.head_pending_event(agent_name)
    if head is None or head.event_type is not InboundEventType.TASK_REPLY:
        return None
    return head


def project_id_for_agent(dispatcher, agent_name: str) -> str | None:
    runtime = dispatcher._registry.get(agent_name)
    if runtime is not None and runtime.project_id:
        return runtime.project_id
    latest = dispatcher.latest_for_agent(agent_name)
    if latest is not None and latest.request.project_id:
        return latest.request.project_id
    return None


def reply_delivery_inbound_event_id(job: JobRecord) -> str | None:
    value = job.provider_options.get(REPLY_DELIVERY_INBOUND_EVENT_OPTION)
    text = str(value or '').strip()
    return text or None


def reply_delivery_reply_id(job: JobRecord) -> str | None:
    value = job.provider_options.get(REPLY_DELIVERY_REPLY_ID_OPTION)
    text = str(value or '').strip()
    return text or None


def is_reply_delivery_job(job: JobRecord) -> bool:
    if str(job.request.message_type or '').strip().lower() == REPLY_DELIVERY_MESSAGE_TYPE:
        return True
    return bool(job.provider_options.get(REPLY_DELIVERY_PROVIDER_OPTION))


def head_reply_id(head) -> str | None:
    if head is None:
        return None
    return reply_id_from_payload(head.payload_ref)


__all__ = [
    'head_reply_event',
    'head_reply_id',
    'is_reply_delivery_job',
    'project_id_for_agent',
    'reply_delivery_inbound_event_id',
    'reply_delivery_reply_id',
]
