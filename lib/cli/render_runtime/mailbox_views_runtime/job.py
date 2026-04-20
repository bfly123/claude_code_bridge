from __future__ import annotations

from collections.abc import Mapping

from ..common import display_text


def render_job_state(payload: Mapping[str, object]) -> tuple[str, ...]:
    keys = (
        'job_id',
        'agent_name',
        'target_kind',
        'target_name',
        'provider',
        'provider_instance',
        'status',
        'reply',
        'completion_reason',
        'completion_confidence',
        'updated_at',
    )
    lines: list[str] = []
    for key in keys:
        value = payload.get(key)
        if key == 'reply':
            value = display_text(value)
        lines.append(f'{key}: {value}')
    return tuple(lines)


def render_pend(payload: Mapping[str, object]) -> tuple[str, ...]:
    lines = list(render_job_state(payload))
    if payload.get('mailbox_reply_ready') is not None:
        lines.extend(
            [
                f'mailbox_reply_ready: {str(bool(payload.get("mailbox_reply_ready"))).lower()}',
                f'mailbox_reply_id: {payload.get("mailbox_reply_id")}',
                f'mailbox_reply_from_agent: {payload.get("mailbox_reply_from_agent")}',
                f'mailbox_reply_terminal_status: {payload.get("mailbox_reply_terminal_status")}',
                f'mailbox_reply_notice: {str(bool(payload.get("mailbox_reply_notice"))).lower()}',
                f'mailbox_reply_notice_kind: {payload.get("mailbox_reply_notice_kind")}',
                f'mailbox_reply_job_id: {payload.get("mailbox_reply_job_id")}',
                f'mailbox_reply_finished_at: {payload.get("mailbox_reply_finished_at")}',
            ]
        )
        if payload.get('mailbox_reply_last_progress_at') is not None:
            lines.append(f'mailbox_reply_last_progress_at: {payload.get("mailbox_reply_last_progress_at")}')
        if payload.get('mailbox_reply_heartbeat_silence_seconds') is not None:
            lines.append(
                f'mailbox_reply_heartbeat_silence_seconds: {payload.get("mailbox_reply_heartbeat_silence_seconds")}'
            )
        if payload.get('mailbox_reply') is not None:
            lines.append(f'mailbox_reply: {display_text(payload.get("mailbox_reply"))}')
    return tuple(lines)


__all__ = ['render_job_state', 'render_pend']
