from __future__ import annotations

from ccbd.api_models import TargetKind

from ..records import get_job
from ..reply_delivery import claim_reply_delivery_start, claimable_reply_delivery_job_ids
from .models import QueuedTargetSlot
from .recovery import refresh_slot_runtime_for_start
from .start import start_running_job


def start_next_queued_job(dispatcher, slot: QueuedTargetSlot):
    slot = refresh_slot_runtime_for_start(dispatcher, slot)
    if slot is None:
        return None
    if dispatcher._message_bureau is not None and slot.target_kind is TargetKind.AGENT:
        return _start_agent_mailbox_job(dispatcher, slot)
    job_id = dispatcher._state.pop_next_for(slot.target_kind, slot.target_name)
    if job_id is None:
        return None
    current = get_job(dispatcher, job_id)
    if current is None:
        return None
    return start_running_job(dispatcher, current, slot=slot)


def _start_agent_mailbox_job(dispatcher, slot: QueuedTargetSlot):
    queued_ids = set(dispatcher._state.queued_items_for(slot.target_kind, slot.target_name))
    reply_delivery = _claim_reply_delivery(dispatcher, slot, queued_ids)
    if reply_delivery is not None:
        return reply_delivery
    job_id = _claim_request_job_id(dispatcher, slot, queued_ids)
    if job_id is None:
        return None
    current = get_job(dispatcher, job_id)
    if current is None:
        return None
    return start_running_job(dispatcher, current, slot=slot)


def _claim_reply_delivery(dispatcher, slot: QueuedTargetSlot, queued_ids: set[str]):
    for candidate in claimable_reply_delivery_job_ids(dispatcher, slot.target_name):
        if candidate not in queued_ids:
            continue
        current = get_job(dispatcher, candidate)
        if current is None:
            dispatcher._state.remove_queued_for(slot.target_kind, slot.target_name, candidate)
            continue
        started_at = dispatcher._clock()
        if not claim_reply_delivery_start(dispatcher, current, started_at=started_at):
            continue
        dispatcher._state.remove_queued_for(slot.target_kind, slot.target_name, candidate)
        return start_running_job(dispatcher, current, slot=slot, started_at=started_at)
    return None


def _claim_request_job_id(dispatcher, slot: QueuedTargetSlot, queued_ids: set[str]) -> str | None:
    for candidate in dispatcher._message_bureau.claimable_request_job_ids(slot.target_name):
        if candidate not in queued_ids:
            continue
        dispatcher._state.remove_queued_for(slot.target_kind, slot.target_name, candidate)
        return candidate
    return None


__all__ = ['start_next_queued_job']
