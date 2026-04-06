from __future__ import annotations

from .targets import (
    COMMAND_MAILBOX_ACTOR,
    COMMAND_MAILBOX_ALIASES,
    NON_MAILBOX_ACTORS,
    USER_ACTOR,
    known_mailbox_targets,
    normalize_actor_name,
    normalize_mailbox_owner_name,
    normalize_mailbox_target,
)

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
