from __future__ import annotations

from message_bureau.reply_payloads import delivery_job_id_from_payload

from ..records import get_job
from .common import head_reply_event, head_reply_id
from .decisions import reply_delivery_failed_decision
from .preparation_head import reset_stale_reply_head


def repair_reply_delivery_heads(dispatcher):
    repaired = []
    for agent_name in dispatcher._config.agents:
        result = repair_agent_reply_delivery_head(dispatcher, agent_name)
        if result is not None:
            repaired.append(result)
    return tuple(repaired)


def repair_agent_reply_delivery_head(dispatcher, agent_name: str):
    head = head_reply_event(dispatcher, agent_name)
    if head is None:
        return None
    reply_id = head_reply_id(head)
    if not reply_id:
        return None

    delivery_job_id = delivery_job_id_from_payload(head.payload_ref)
    if not delivery_job_id:
        return _repair_orphaned_lease(dispatcher, head, reply_id=reply_id, agent_name=agent_name)

    current = get_job(dispatcher, delivery_job_id)
    if current is None:
        return reset_stale_reply_head(
            dispatcher,
            head,
            reply_id=reply_id,
            agent_name=agent_name,
        )

    if current.status.value != 'running':
        return None

    persisted = _load_persisted_execution_state(dispatcher, current.job_id)
    if persisted is not None and persisted.pending_decision is not None and persisted.pending_decision.terminal:
        return dispatcher.complete(current.job_id, persisted.pending_decision)
    if _execution_job_is_live(dispatcher, current.job_id):
        return None

    return dispatcher.complete(
        current.job_id,
        reply_delivery_failed_decision(
            current,
            finished_at=dispatcher._clock(),
            reason='reply_delivery_stale_running_repaired',
            diagnostics={
                'repair_kind': 'stale_running_delivery_job',
                'head_inbound_event_id': head.inbound_event_id,
                'reply_id': reply_id,
            },
        ),
    )


def _repair_orphaned_lease(dispatcher, head, *, reply_id: str, agent_name: str):
    lease = dispatcher._message_bureau_control._lease_store.load(agent_name)
    if lease is None:
        return None
    if lease.inbound_event_id != head.inbound_event_id:
        return None
    return reset_stale_reply_head(
        dispatcher,
        head,
        reply_id=reply_id,
        agent_name=agent_name,
    )


def _load_persisted_execution_state(dispatcher, job_id: str):
    execution = getattr(dispatcher, '_execution_service', None)
    if execution is None:
        return None
    state_store = getattr(execution, '_state_store', None)
    if state_store is None:
        return None
    try:
        return state_store.load(job_id)
    except Exception:
        return None


def _execution_job_is_live(dispatcher, job_id: str) -> bool:
    execution = getattr(dispatcher, '_execution_service', None)
    if execution is None:
        return False
    try:
        active = getattr(execution, '_active', None)
        if isinstance(active, dict) and job_id in active:
            return True
    except Exception:
        return False
    try:
        pending_replays = getattr(execution, '_pending_replays', None)
        if isinstance(pending_replays, dict) and job_id in pending_replays:
            return True
    except Exception:
        return False
    return False


__all__ = ['repair_reply_delivery_heads']
