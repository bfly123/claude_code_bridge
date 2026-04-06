from __future__ import annotations

from .agent import agent_queue
from ..common import require_mailbox_target
from ..events import inbox_item_summary, pending_event_records


def inbox(service, agent_name: str) -> dict[str, object]:
    normalized = require_mailbox_target(service, agent_name)
    mailbox_payload = agent_queue(service, normalized)
    records = pending_event_records(service, normalized)
    items = [inbox_item_summary(service, record, position=index) for index, record in enumerate(records, start=1)]
    head = items[0] if items else None
    return {
        'target': normalized,
        'agent': mailbox_payload,
        'item_count': len(items),
        'head': head,
        'items': items,
    }


__all__ = ['inbox']
