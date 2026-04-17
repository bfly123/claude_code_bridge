from __future__ import annotations

from mailbox_runtime.targets import normalize_mailbox_target
from mailbox_kernel import MailboxState


def derive_mailbox_state(has_active: bool, queue_depth: int) -> str:
    if has_active:
        return MailboxState.DELIVERING.value
    if queue_depth > 0:
        return MailboxState.BLOCKED.value
    return MailboxState.IDLE.value


def require_mailbox_target(service, agent_name: str) -> str:
    normalized = normalize_mailbox_target(agent_name, known_targets=service._known_mailboxes)
    if normalized is None:
        raise ValueError(f'unknown mailbox target: {str(agent_name or "").strip().lower()}')
    return normalized


def summary_targets(service) -> tuple[str, ...]:
    targets = set(getattr(service._config, 'agents', {}).keys())
    for mailbox_name in getattr(service, '_known_mailboxes', frozenset()):
        if mailbox_name in targets:
            continue
        if mailbox_has_activity(service, mailbox_name):
            targets.add(mailbox_name)
    return tuple(sorted(targets))


def mailbox_has_activity(service, agent_name: str) -> bool:
    from .events import pending_event_records

    return bool(pending_event_records(service, agent_name))


def preview_text(value: str, *, limit: int = 120) -> str:
    text = str(value or '').replace('\r', '').replace('\n', '\\n').strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + '...'


__all__ = [
    'derive_mailbox_state',
    'mailbox_has_activity',
    'preview_text',
    'require_mailbox_target',
    'summary_targets',
]
