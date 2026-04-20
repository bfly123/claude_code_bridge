from __future__ import annotations

from typing import Any

from agents.models import (
    AgentSpec,
    AgentValidationError,
    PermissionMode,
    ProviderProfileSpec,
    QueuePolicy,
    RestoreMode,
    RuntimeMode,
    WorkspaceMode,
    normalize_runtime_mode,
)

from ..common import ALLOWED_AGENT_KEYS, ConfigValidationError
from .expectations import expect_mapping, expect_string, expect_string_list, expect_string_mapping
from .provider_profiles import parse_provider_profile


def build_agent_spec(agent_name: str, raw: dict[str, Any]) -> AgentSpec:
    unknown = sorted(set(raw) - ALLOWED_AGENT_KEYS)
    if unknown:
        raise ConfigValidationError(
            f'agents.{agent_name} contains unknown fields: {", ".join(unknown)}'
        )
    provider = expect_string(raw.get('provider'), field_name=f'agents.{agent_name}.provider')
    try:
        return AgentSpec(
            name=agent_name,
            provider=provider,
            target=expect_string(raw.get('target'), field_name=f'agents.{agent_name}.target'),
            workspace_mode=WorkspaceMode(
                expect_string(raw.get('workspace_mode'), field_name=f'agents.{agent_name}.workspace_mode')
            ),
            workspace_root=(
                expect_string(raw['workspace_root'], field_name=f'agents.{agent_name}.workspace_root')
                if raw.get('workspace_root') is not None
                else None
            ),
            runtime_mode=normalize_runtime_mode(
                expect_string(
                    raw.get('runtime_mode', RuntimeMode.PANE_BACKED.value),
                    field_name=f'agents.{agent_name}.runtime_mode',
                )
            ),
            restore_default=RestoreMode(
                expect_string(raw.get('restore'), field_name=f'agents.{agent_name}.restore')
            ),
            permission_default=PermissionMode(
                expect_string(raw.get('permission'), field_name=f'agents.{agent_name}.permission')
            ),
            queue_policy=QueuePolicy(str(raw.get('queue_policy') or QueuePolicy.SERIAL_PER_AGENT.value)),
            startup_args=expect_string_list(raw.get('startup_args', []), field_name=f'agents.{agent_name}.startup_args'),
            env=expect_string_mapping(raw.get('env', {}), field_name=f'agents.{agent_name}.env'),
            provider_profile=(
                parse_provider_profile(agent_name, raw['provider_profile'])
                if raw.get('provider_profile') is not None
                else ProviderProfileSpec()
            ),
            branch_template=(
                expect_string(raw['branch_template'], field_name=f'agents.{agent_name}.branch_template')
                if raw.get('branch_template') is not None
                else None
            ),
            labels=expect_string_list(raw.get('labels', []), field_name=f'agents.{agent_name}.labels'),
            description=(
                expect_string(raw['description'], field_name=f'agents.{agent_name}.description')
                if raw.get('description') is not None
                else None
            ),
            watch_paths=expect_string_list(raw.get('watch_paths', []), field_name=f'agents.{agent_name}.watch_paths'),
        )
    except AgentValidationError as exc:
        raise ConfigValidationError(str(exc)) from exc
    except ValueError as exc:
        raise ConfigValidationError(f'agents.{agent_name}: {exc}') from exc


def parse_agents(raw_agents: Any) -> dict[str, AgentSpec]:
    from agents.models import normalize_agent_name

    raw_agents_map = expect_mapping(raw_agents, field_name='agents')
    parsed_agents: dict[str, AgentSpec] = {}
    for raw_name, raw_spec in raw_agents_map.items():
        if not isinstance(raw_name, str):
            raise ConfigValidationError('agents table keys must be strings')
        try:
            normalized_name = normalize_agent_name(raw_name)
        except AgentValidationError as exc:
            raise ConfigValidationError(str(exc)) from exc
        if normalized_name in parsed_agents:
            raise ConfigValidationError(f'duplicate agent name after normalization: {normalized_name}')
        parsed_agents[normalized_name] = build_agent_spec(
            normalized_name,
            expect_mapping(raw_spec, field_name=f'agents.{raw_name}'),
        )
    return parsed_agents


__all__ = ['build_agent_spec', 'parse_agents']
