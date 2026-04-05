from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.models import (
    AgentSpec,
    AgentValidationError,
    PermissionMode,
    ProjectConfig,
    ProviderProfileSpec,
    QueuePolicy,
    RestoreMode,
    RuntimeMode,
    WorkspaceMode,
    normalize_agent_name,
    normalize_runtime_mode,
)

from .common import (
    ALLOWED_AGENT_KEYS,
    ALLOWED_PROVIDER_PROFILE_KEYS,
    ALLOWED_TOP_LEVEL_KEYS,
    ConfigValidationError,
)


def _expect_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigValidationError(f'{field_name} must be a table/object')
    return dict(value)


def _expect_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ConfigValidationError(f'{field_name} must be a string')
    text = value.strip()
    if not text:
        raise ConfigValidationError(f'{field_name} cannot be empty')
    return text


def _expect_bool(value: Any, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigValidationError(f'{field_name} must be a boolean')
    return value


def _expect_string_list(value: Any, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ConfigValidationError(f'{field_name} must be a list of strings')
    items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ConfigValidationError(f'{field_name}[{index}] must be a string')
        text = item.strip()
        if not text:
            raise ConfigValidationError(f'{field_name}[{index}] cannot be empty')
        items.append(text)
    return tuple(items)


def _expect_string_mapping(value: Any, *, field_name: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ConfigValidationError(f'{field_name} must be a table of strings')
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ConfigValidationError(f'{field_name} keys must be strings')
        if not isinstance(item, str):
            raise ConfigValidationError(f'{field_name}.{key} must be a string')
        result[str(key)] = item
    return result


def _parse_provider_profile(agent_name: str, value: Any) -> ProviderProfileSpec:
    raw = _expect_mapping(value, field_name=f'agents.{agent_name}.provider_profile')
    unknown = sorted(set(raw) - ALLOWED_PROVIDER_PROFILE_KEYS)
    if unknown:
        raise ConfigValidationError(
            f'agents.{agent_name}.provider_profile contains unknown fields: {", ".join(unknown)}'
        )
    try:
        return ProviderProfileSpec(
            mode=(
                _expect_string(raw['mode'], field_name=f'agents.{agent_name}.provider_profile.mode')
                if raw.get('mode') is not None
                else 'inherit'
            ),
            home=(
                _expect_string(raw['home'], field_name=f'agents.{agent_name}.provider_profile.home')
                if raw.get('home') is not None
                else None
            ),
            env=_expect_string_mapping(
                raw.get('env', {}),
                field_name=f'agents.{agent_name}.provider_profile.env',
            ),
            inherit_api=(
                _expect_bool(raw['inherit_api'], field_name=f'agents.{agent_name}.provider_profile.inherit_api')
                if 'inherit_api' in raw
                else True
            ),
            inherit_auth=(
                _expect_bool(raw['inherit_auth'], field_name=f'agents.{agent_name}.provider_profile.inherit_auth')
                if 'inherit_auth' in raw
                else True
            ),
            inherit_config=(
                _expect_bool(raw['inherit_config'], field_name=f'agents.{agent_name}.provider_profile.inherit_config')
                if 'inherit_config' in raw
                else True
            ),
            inherit_skills=(
                _expect_bool(raw['inherit_skills'], field_name=f'agents.{agent_name}.provider_profile.inherit_skills')
                if 'inherit_skills' in raw
                else True
            ),
            inherit_commands=(
                _expect_bool(raw['inherit_commands'], field_name=f'agents.{agent_name}.provider_profile.inherit_commands')
                if 'inherit_commands' in raw
                else True
            ),
        )
    except ValueError as exc:
        raise ConfigValidationError(f'agents.{agent_name}.provider_profile: {exc}') from exc


def _build_agent_spec(agent_name: str, raw: dict[str, Any]) -> AgentSpec:
    unknown = sorted(set(raw) - ALLOWED_AGENT_KEYS)
    if unknown:
        raise ConfigValidationError(
            f'agents.{agent_name} contains unknown fields: {", ".join(unknown)}'
        )
    provider = _expect_string(raw.get('provider'), field_name=f'agents.{agent_name}.provider')
    try:
        return AgentSpec(
            name=agent_name,
            provider=provider,
            target=_expect_string(raw.get('target'), field_name=f'agents.{agent_name}.target'),
            workspace_mode=WorkspaceMode(
                _expect_string(raw.get('workspace_mode'), field_name=f'agents.{agent_name}.workspace_mode')
            ),
            workspace_root=(
                _expect_string(raw['workspace_root'], field_name=f'agents.{agent_name}.workspace_root')
                if raw.get('workspace_root') is not None
                else None
            ),
            runtime_mode=normalize_runtime_mode(
                _expect_string(
                    raw.get('runtime_mode', RuntimeMode.PANE_BACKED.value),
                    field_name=f'agents.{agent_name}.runtime_mode',
                )
            ),
            restore_default=RestoreMode(
                _expect_string(raw.get('restore'), field_name=f'agents.{agent_name}.restore')
            ),
            permission_default=PermissionMode(
                _expect_string(raw.get('permission'), field_name=f'agents.{agent_name}.permission')
            ),
            queue_policy=QueuePolicy(str(raw.get('queue_policy') or QueuePolicy.SERIAL_PER_AGENT.value)),
            startup_args=_expect_string_list(raw.get('startup_args', []), field_name=f'agents.{agent_name}.startup_args'),
            env=_expect_string_mapping(raw.get('env', {}), field_name=f'agents.{agent_name}.env'),
            provider_profile=(
                _parse_provider_profile(agent_name, raw['provider_profile'])
                if raw.get('provider_profile') is not None
                else ProviderProfileSpec()
            ),
            branch_template=(
                _expect_string(raw['branch_template'], field_name=f'agents.{agent_name}.branch_template')
                if raw.get('branch_template') is not None
                else None
            ),
            labels=_expect_string_list(raw.get('labels', []), field_name=f'agents.{agent_name}.labels'),
            description=(
                _expect_string(raw['description'], field_name=f'agents.{agent_name}.description')
                if raw.get('description') is not None
                else None
            ),
            watch_paths=_expect_string_list(raw.get('watch_paths', []), field_name=f'agents.{agent_name}.watch_paths'),
        )
    except AgentValidationError as exc:
        raise ConfigValidationError(str(exc)) from exc
    except ValueError as exc:
        raise ConfigValidationError(f'agents.{agent_name}: {exc}') from exc


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
            for item in _expect_string_list(raw_default_agents, field_name='default_agents')
        )
    except AgentValidationError as exc:
        raise ConfigValidationError(str(exc)) from exc

    raw_agents = _expect_mapping(document.get('agents'), field_name='agents')
    parsed_agents: dict[str, AgentSpec] = {}
    for raw_name, raw_spec in raw_agents.items():
        if not isinstance(raw_name, str):
            raise ConfigValidationError('agents table keys must be strings')
        try:
            normalized_name = normalize_agent_name(raw_name)
        except AgentValidationError as exc:
            raise ConfigValidationError(str(exc)) from exc
        if normalized_name in parsed_agents:
            raise ConfigValidationError(f'duplicate agent name after normalization: {normalized_name}')
        spec = _build_agent_spec(normalized_name, _expect_mapping(raw_spec, field_name=f'agents.{raw_name}'))
        parsed_agents[normalized_name] = spec

    try:
        return ProjectConfig(
            version=2,
            default_agents=default_agents,
            agents=parsed_agents,
            cmd_enabled=(
                _expect_bool(document['cmd_enabled'], field_name='cmd_enabled')
                if 'cmd_enabled' in document
                else False
            ),
            layout_spec=(
                _expect_string(document['layout'], field_name='layout')
                if document.get('layout') is not None
                else None
            ),
            source_path=str(source_path) if source_path else None,
        )
    except AgentValidationError as exc:
        raise ConfigValidationError(str(exc)) from exc


__all__ = ['validate_project_config']
