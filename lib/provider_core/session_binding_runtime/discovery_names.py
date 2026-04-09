from __future__ import annotations

from agents.models import normalize_agent_name


def normalized_filename(value: str) -> str:
    return str(value or '').strip()


def session_prefix(base_filename: str) -> str:
    base = normalized_filename(base_filename)
    if base.endswith('-session'):
        return base[: -len('-session')]
    return base


def named_pattern(base_filename: str) -> str:
    prefix = session_prefix(base_filename)
    if not prefix:
        return ''
    return f'{prefix}-*-session'


def session_filename_matches(*, base_filename: str, filename: str) -> bool:
    name = normalized_filename(filename)
    base = normalized_filename(base_filename)
    if not name or not base:
        return False
    if name == base:
        return True
    prefix = session_prefix(base)
    return bool(prefix and name.startswith(f'{prefix}-') and name.endswith('-session'))


def agent_name_from_session_filename(
    *,
    provider: str,
    base_filename: str,
    filename: str,
) -> str | None:
    del provider
    name = normalized_filename(filename)
    base = normalized_filename(base_filename)
    if not session_filename_matches(base_filename=base, filename=name):
        return None
    if name == base:
        return None
    prefix = session_prefix(base)
    if not prefix:
        return None
    raw = name[len(prefix) + 1 : -len('-session')]
    normalized = normalize_agent_name(raw)
    return normalized or None


__all__ = [
    'agent_name_from_session_filename',
    'named_pattern',
    'normalized_filename',
    'session_filename_matches',
    'session_prefix',
]
