from __future__ import annotations

import re

SCHEMA_VERSION = 2
AGENT_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]{0,31}$')
RESERVED_AGENT_NAMES = frozenset(
    {
        'all',
        'from',
        'user',
        'system',
        'ask',
        'cancel',
        'pend',
        'ping',
        'watch',
        'kill',
        'ps',
        'logs',
        'doctor',
        'config',
        'cmd',
        'version',
        'update',
        'help',
    }
)


class AgentValidationError(ValueError):
    pass


def normalize_agent_name(name: str) -> str:
    value = (name or '').strip()
    if not value:
        raise AgentValidationError('agent name cannot be empty')
    if not AGENT_NAME_PATTERN.fullmatch(value):
        raise AgentValidationError(
            'agent name must match ^[a-zA-Z][a-zA-Z0-9_-]{0,31}$'
        )
    normalized = value.lower()
    if normalized in RESERVED_AGENT_NAMES:
        raise AgentValidationError(f'agent name {normalized!r} is reserved')
    return normalized


def validate_agent_name(name: str) -> str:
    return normalize_agent_name(name)


__all__ = [
    'AGENT_NAME_PATTERN',
    'RESERVED_AGENT_NAMES',
    'SCHEMA_VERSION',
    'AgentValidationError',
    'normalize_agent_name',
    'validate_agent_name',
]
