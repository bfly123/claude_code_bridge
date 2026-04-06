from __future__ import annotations

from .agent import agent_queue
from ..common import summary_targets


def queue_summary(service, target: str = 'all') -> dict[str, object]:
    normalized = str(target or '').strip().lower() or 'all'
    if normalized != 'all':
        return {'target': normalized, 'agent': agent_queue(service, normalized)}
    agent_summaries = [agent_queue(service, agent_name) for agent_name in summary_targets(service)]
    return {
        'target': 'all',
        'agent_count': len(agent_summaries),
        'queued_agent_count': sum(1 for item in agent_summaries if int(item['queue_depth']) > 0),
        'active_agent_count': sum(1 for item in agent_summaries if item['active_inbound_event_id'] is not None),
        'total_queue_depth': sum(int(item['queue_depth']) for item in agent_summaries),
        'total_pending_reply_count': sum(int(item['pending_reply_count']) for item in agent_summaries),
        'agents': agent_summaries,
    }


__all__ = ['queue_summary']
