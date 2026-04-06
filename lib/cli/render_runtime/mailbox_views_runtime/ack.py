from __future__ import annotations

from collections.abc import Mapping

from ..common import display_text


def render_ack(payload: Mapping[str, object]) -> tuple[str, ...]:
    mailbox = payload.get('mailbox') or {}
    lines: list[str] = [
        'ack_status: ok',
        f'target: {payload.get("target")}',
        f'agent_name: {payload.get("agent_name")}',
        f'acknowledged_inbound_event_id: {payload.get("acknowledged_inbound_event_id")}',
        f'message_id: {payload.get("message_id")}',
        f'attempt_id: {payload.get("attempt_id")}',
        f'job_id: {payload.get("job_id")}',
        f'reply_id: {payload.get("reply_id")}',
        f'reply_from_agent: {payload.get("reply_from_agent")}',
        f'reply_terminal_status: {payload.get("reply_terminal_status")}',
        f'reply_notice: {str(bool(payload.get("reply_notice"))).lower()}',
        f'reply_notice_kind: {payload.get("reply_notice_kind")}',
        f'reply_finished_at: {payload.get("reply_finished_at")}',
        f'mailbox_state: {mailbox.get("mailbox_state")}',
        f'queue_depth: {mailbox.get("queue_depth")}',
        f'pending_reply_count: {mailbox.get("pending_reply_count")}',
        f'next_inbound_event_id: {payload.get("next_inbound_event_id")}',
        f'next_event_type: {payload.get("next_event_type")}',
    ]
    if payload.get('reply_last_progress_at') is not None:
        lines.append(f'reply_last_progress_at: {payload.get("reply_last_progress_at")}')
    if payload.get('reply_heartbeat_silence_seconds') is not None:
        lines.append(f'reply_heartbeat_silence_seconds: {payload.get("reply_heartbeat_silence_seconds")}')
    lines.append(f'reply: {display_text(payload.get("reply"))}')
    return tuple(lines)


__all__ = ['render_ack']
