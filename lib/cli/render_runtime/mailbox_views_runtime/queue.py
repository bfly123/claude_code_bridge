from __future__ import annotations

from collections.abc import Mapping


def render_queue(payload: Mapping[str, object]) -> tuple[str, ...]:
    lines: list[str] = [
        'queue_status: ok',
        f'target: {payload.get("target")}',
    ]
    if payload.get('target') == 'all':
        lines.extend(
            [
                f'agent_count: {payload.get("agent_count")}',
                f'queued_agent_count: {payload.get("queued_agent_count")}',
                f'active_agent_count: {payload.get("active_agent_count")}',
                f'total_queue_depth: {payload.get("total_queue_depth")}',
                f'total_pending_reply_count: {payload.get("total_pending_reply_count")}',
            ]
        )
        agents = payload.get('agents') or ()
        for agent in agents:
            lines.append(
                'queue_agent: '
                f'name={agent["agent_name"]} runtime_state={agent.get("runtime_state")} '
                f'runtime_health={agent.get("runtime_health")} state={agent["mailbox_state"]} '
                f'depth={agent["queue_depth"]} pending_replies={agent["pending_reply_count"]}'
            )
        return tuple(lines)

    agent = payload.get('agent') or {}
    lines.extend(
        [
            f'agent_name: {agent.get("agent_name")}',
            f'mailbox_id: {agent.get("mailbox_id")}',
            f'mailbox_state: {agent.get("mailbox_state")}',
            f'runtime_state: {agent.get("runtime_state")}',
            f'runtime_health: {agent.get("runtime_health")}',
            f'lease_version: {agent.get("lease_version")}',
            f'queue_depth: {agent.get("queue_depth")}',
            f'pending_reply_count: {agent.get("pending_reply_count")}',
            f'active_inbound_event_id: {agent.get("active_inbound_event_id")}',
            f'last_inbound_started_at: {agent.get("last_inbound_started_at")}',
            f'last_inbound_finished_at: {agent.get("last_inbound_finished_at")}',
        ]
    )
    active = agent.get('active')
    if isinstance(active, Mapping):
        lines.append(
            'queue_active: '
            f'event={active.get("inbound_event_id")} type={active.get("event_type")} status={active.get("status")} '
            f'message={active.get("message_id")} attempt={active.get("attempt_id")} job={active.get("job_id")}'
        )
    for event in agent.get('queued_events') or ():
        lines.append(
            'queue_event: '
            f'pos={event["position"]} event={event["inbound_event_id"]} type={event["event_type"]} '
            f'status={event["status"]} priority={event["priority"]} '
            f'message={event["message_id"]} attempt={event["attempt_id"]} job={event["job_id"]}'
        )
    return tuple(lines)


__all__ = ['render_queue']
