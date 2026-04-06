from __future__ import annotations

from collections.abc import Mapping

from ..common import display_text


def render_inbox(payload: Mapping[str, object]) -> tuple[str, ...]:
    agent = payload.get('agent') or {}
    head = payload.get('head') or {}
    lines: list[str] = [
        'inbox_status: ok',
        f'target: {payload.get("target")}',
        f'agent_name: {agent.get("agent_name")}',
        f'mailbox_id: {agent.get("mailbox_id")}',
        f'mailbox_state: {agent.get("mailbox_state")}',
        f'lease_version: {agent.get("lease_version")}',
        f'queue_depth: {agent.get("queue_depth")}',
        f'pending_reply_count: {agent.get("pending_reply_count")}',
        f'active_inbound_event_id: {agent.get("active_inbound_event_id")}',
        f'item_count: {payload.get("item_count")}',
        f'head_inbound_event_id: {head.get("inbound_event_id")}',
        f'head_event_type: {head.get("event_type")}',
        f'head_status: {head.get("status")}',
    ]
    if head.get('reply_id') is not None:
        lines.extend(
            [
                f'head_reply_id: {head.get("reply_id")}',
                f'head_reply_from_agent: {head.get("source_actor")}',
                f'head_reply_terminal_status: {head.get("reply_terminal_status")}',
                f'head_reply_notice: {str(bool(head.get("reply_notice"))).lower()}',
                f'head_reply_notice_kind: {head.get("reply_notice_kind")}',
                f'head_reply_job_id: {head.get("job_id")}',
                f'head_reply_finished_at: {head.get("reply_finished_at")}',
            ]
        )
        if head.get('reply_last_progress_at') is not None:
            lines.append(f'head_reply_last_progress_at: {head.get("reply_last_progress_at")}')
        if head.get('reply_heartbeat_silence_seconds') is not None:
            lines.append(f'head_reply_heartbeat_silence_seconds: {head.get("reply_heartbeat_silence_seconds")}')
    if head.get('reply') is not None:
        lines.append(f'reply: {display_text(head.get("reply"))}')
    for item in payload.get('items') or ():
        parts = [
            'inbox_item:',
            f'pos={item.get("position")}',
            f'event={item.get("inbound_event_id")}',
            f'type={item.get("event_type")}',
            f'status={item.get("status")}',
            f'priority={item.get("priority")}',
            f'message={item.get("message_id")}',
            f'attempt={item.get("attempt_id")}',
            f'job={item.get("job_id")}',
            f'from={item.get("source_actor")}',
        ]
        if item.get('reply_id') is not None:
            parts.extend(
                [
                    f'reply={item.get("reply_id")}',
                    f'terminal={item.get("reply_terminal_status")}',
                    f'notice={str(bool(item.get("reply_notice"))).lower()}',
                    f'kind={item.get("reply_notice_kind")}',
                    f'control_job={item.get("job_id")}',
                    f'preview={item.get("reply_preview")}',
                ]
            )
        lines.append(' '.join(parts))
    return tuple(lines)


__all__ = ['render_inbox']
