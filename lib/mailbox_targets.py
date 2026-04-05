from __future__ import annotations

from agents.models import AgentValidationError, normalize_agent_name

COMMAND_MAILBOX_ACTOR = 'cmd'
USER_ACTOR = 'user'
NON_MAILBOX_ACTORS = frozenset({'system', 'manual', 'email'})
COMMAND_MAILBOX_ALIASES = frozenset({COMMAND_MAILBOX_ACTOR})


def normalize_actor_name(actor: str | None) -> str:
    normalized = str(actor or '').strip().lower()
    if not normalized:
        raise AgentValidationError('actor cannot be empty')
    if normalized in COMMAND_MAILBOX_ALIASES:
        return COMMAND_MAILBOX_ACTOR
    if normalized == USER_ACTOR or normalized in NON_MAILBOX_ACTORS:
        return normalized
    return normalize_agent_name(normalized)


def normalize_mailbox_owner_name(actor: str | None) -> str:
    normalized = normalize_actor_name(actor)
    if normalized == USER_ACTOR or normalized in NON_MAILBOX_ACTORS:
        raise AgentValidationError(f'actor {normalized!r} does not own a mailbox')
    return normalized


def known_mailbox_targets(config) -> frozenset[str]:
    agents = getattr(config, 'agents', {}) or {}
    targets = {COMMAND_MAILBOX_ACTOR}
    targets.update(normalize_agent_name(name) for name in agents)
    return frozenset(targets)


def normalize_mailbox_target(actor: str | None, *, known_targets: frozenset[str]) -> str | None:
    normalized = str(actor or '').strip().lower()
    if not normalized:
        return None
    try:
        mailbox_name = normalize_mailbox_owner_name(normalized)
    except AgentValidationError:
        return None
    if mailbox_name in known_targets:
        return mailbox_name
    return None


__all__ = [
    'COMMAND_MAILBOX_ACTOR',
    'COMMAND_MAILBOX_ALIASES',
    'NON_MAILBOX_ACTORS',
    'USER_ACTOR',
    'known_mailbox_targets',
    'normalize_actor_name',
    'normalize_mailbox_owner_name',
    'normalize_mailbox_target',
]
