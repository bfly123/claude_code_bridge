from __future__ import annotations

from typing import Any

from agents.models import AgentApiSpec

from ..common import ConfigValidationError
from .expectations import expect_mapping, expect_string

_ALLOWED_AGENT_API_KEYS = {'key', 'url'}


def parse_agent_api(agent_name: str, value: Any) -> AgentApiSpec:
    raw = expect_mapping(value, field_name=f'agents.{agent_name}.api')
    parsed: dict[str, str] = {}
    for raw_key, raw_value in raw.items():
        field_name = _normalize_agent_api_field(agent_name, raw_key)
        if field_name in parsed:
            raise ConfigValidationError(f'agents.{agent_name}.api contains duplicate field: {field_name}')
        parsed[field_name] = expect_string(raw_value, field_name=f'agents.{agent_name}.api.{field_name}')
    api = AgentApiSpec(**parsed)
    if api == AgentApiSpec():
        allowed = ', '.join(sorted(_ALLOWED_AGENT_API_KEYS))
        raise ConfigValidationError(f'agents.{agent_name}.api must define at least one of: {allowed}')
    return api


def _normalize_agent_api_field(agent_name: str, raw_key: object) -> str:
    if not isinstance(raw_key, str):
        raise ConfigValidationError(f'agents.{agent_name}.api keys must be strings')
    normalized = raw_key.strip().lower()
    if normalized not in _ALLOWED_AGENT_API_KEYS:
        allowed = ', '.join(sorted(_ALLOWED_AGENT_API_KEYS))
        raise ConfigValidationError(
            f'agents.{agent_name}.api contains unknown fields: {raw_key}; allowed: {allowed}'
        )
    return normalized


def parse_agent_api_shortcut(agent_name: str, raw_agent: dict[str, Any]) -> AgentApiSpec:
    has_nested_api = raw_agent.get('api') is not None
    has_flat_api = any(raw_agent.get(field) is not None for field in _ALLOWED_AGENT_API_KEYS)
    if has_nested_api and has_flat_api:
        raise ConfigValidationError(
            f'agents.{agent_name}.key/url cannot be combined with agents.{agent_name}.api'
        )
    if has_nested_api:
        return parse_agent_api(agent_name, raw_agent['api'])
    if not has_flat_api:
        return AgentApiSpec()
    return AgentApiSpec(
        key=(
            expect_string(raw_agent['key'], field_name=f'agents.{agent_name}.key')
            if raw_agent.get('key') is not None
            else None
        ),
        url=(
            expect_string(raw_agent['url'], field_name=f'agents.{agent_name}.url')
            if raw_agent.get('url') is not None
            else None
        ),
    )


__all__ = ['parse_agent_api', 'parse_agent_api_shortcut']
