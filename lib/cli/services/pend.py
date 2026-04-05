from __future__ import annotations

from ccbd.socket_client import CcbdClientError
from cli.context import CliContext
from cli.models import ParsedPendCommand

from .daemon import connect_mounted_daemon


def pend_target(context: CliContext, command: ParsedPendCommand) -> dict:
    handle = connect_mounted_daemon(context, allow_restart_stale=True)
    assert handle.client is not None
    try:
        return _pend_target_with_client(handle.client, command.target)
    except CcbdClientError:
        handle = connect_mounted_daemon(context, allow_restart_stale=True)
        assert handle.client is not None
        return _pend_target_with_client(handle.client, command.target)


def _pend_target_with_client(client, target: str) -> dict:
    normalized = str(target or '').strip()
    if normalized.startswith('job_'):
        return client.get(normalized)

    inbox_head = _safe_inbox_head(client, normalized)
    try:
        payload = client.request('get', {'agent_name': normalized})
    except CcbdClientError:
        if inbox_head is None:
            raise
        return _mailbox_reply_payload(normalized, inbox_head)

    if inbox_head is not None:
        payload = dict(payload)
        payload.update(_mailbox_overlay_fields(inbox_head))
    return payload


def _safe_inbox_head(client, agent_name: str) -> dict | None:
    inbox_fn = getattr(client, 'inbox', None)
    if not callable(inbox_fn):
        return None
    try:
        payload = inbox_fn(agent_name)
    except Exception:
        return None
    head = payload.get('head')
    if not isinstance(head, dict) or head.get('reply_id') is None:
        return None
    return head


def _mailbox_reply_payload(agent_name: str, head: dict) -> dict:
    return {
        'job_id': head.get('job_id'),
        'agent_name': agent_name,
        'target_kind': 'agent',
        'target_name': agent_name,
        'provider_instance': None,
        'provider': None,
        'status': 'mailbox_reply',
        'job': None,
        'snapshot': None,
        'reply': '',
        'completion_reason': None,
        'completion_confidence': None,
        'updated_at': head.get('reply_finished_at'),
        **_mailbox_overlay_fields(head),
    }


def _mailbox_overlay_fields(head: dict) -> dict[str, object]:
    return {
        'mailbox_reply_ready': True,
        'mailbox_reply_id': head.get('reply_id'),
        'mailbox_reply_from_agent': head.get('source_actor'),
        'mailbox_reply_terminal_status': head.get('reply_terminal_status'),
        'mailbox_reply_finished_at': head.get('reply_finished_at'),
        'mailbox_reply_notice': bool(head.get('reply_notice')),
        'mailbox_reply_notice_kind': head.get('reply_notice_kind'),
        'mailbox_reply_job_id': head.get('job_id'),
        'mailbox_reply_last_progress_at': head.get('reply_last_progress_at'),
        'mailbox_reply_heartbeat_silence_seconds': head.get('reply_heartbeat_silence_seconds'),
        'mailbox_reply': head.get('reply'),
    }
