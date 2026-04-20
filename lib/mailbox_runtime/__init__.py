from __future__ import annotations

from .targets import (
    CMD_ACTOR,
    NON_AGENT_ACTORS,
    NON_MAILBOX_ACTORS,
    USER_ACTOR,
    known_mailbox_targets,
    normalize_actor_name,
    normalize_mailbox_owner_name,
    normalize_mailbox_target,
)

__all__ = [
    'CMD_ACTOR',
    'NON_AGENT_ACTORS',
    'NON_MAILBOX_ACTORS',
    'USER_ACTOR',
    'known_mailbox_targets',
    'normalize_actor_name',
    'normalize_mailbox_owner_name',
    'normalize_mailbox_target',
]
