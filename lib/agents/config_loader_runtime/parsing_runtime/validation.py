from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.models import AgentValidationError, ProjectConfig, normalize_agent_name

from ..common import ALLOWED_TOP_LEVEL_KEYS, ConfigValidationError
from .agent_specs import parse_agents
from .expectations import expect_bool, expect_string, expect_string_list


def validate_project_config(document: dict[str, Any], *, source_path: Path | None = None) -> ProjectConfig:
    unknown_top = sorted(set(document) - ALLOWED_TOP_LEVEL_KEYS)
    if unknown_top:
        raise ConfigValidationError(
            f'config contains unknown top-level fields: {", ".join(unknown_top)}'
        )
    version = document.get('version')
    if version != 2:
        raise ConfigValidationError('version must be 2')

    raw_default_agents = document.get('default_agents')
    if raw_default_agents is None:
        raise ConfigValidationError('default_agents is required')
    try:
        default_agents = tuple(
            normalize_agent_name(item)
            for item in expect_string_list(raw_default_agents, field_name='default_agents')
        )
    except AgentValidationError as exc:
        raise ConfigValidationError(str(exc)) from exc

    parsed_agents = parse_agents(document.get('agents'))

    try:
        return ProjectConfig(
            version=2,
            default_agents=default_agents,
            agents=parsed_agents,
            cmd_enabled=(
                expect_bool(document['cmd_enabled'], field_name='cmd_enabled')
                if 'cmd_enabled' in document
                else False
            ),
            layout_spec=(
                expect_string(document['layout'], field_name='layout')
                if document.get('layout') is not None
                else None
            ),
            source_path=str(source_path) if source_path else None,
        )
    except AgentValidationError as exc:
        raise ConfigValidationError(str(exc)) from exc


__all__ = ['validate_project_config']
