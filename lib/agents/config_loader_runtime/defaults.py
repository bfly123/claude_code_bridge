from __future__ import annotations

import json

from agents.models import (
    AgentSpec,
    PermissionMode,
    ProjectConfig,
    ProviderProfileSpec,
    QueuePolicy,
    RestoreMode,
    RuntimeMode,
    WorkspaceMode,
)

from .common import DEFAULT_AGENT_ORDER, DEFAULT_DEFAULT_AGENTS

DEFAULT_AGENT_PROVIDERS = (
    ('agent1', 'codex'),
    ('agent2', 'codex'),
    ('agent3', 'claude'),
)


def build_default_project_config() -> ProjectConfig:
    agents: dict[str, AgentSpec] = {}
    for name, provider in DEFAULT_AGENT_PROVIDERS:
        agents[name] = AgentSpec(
            name=name,
            provider=provider,
            target='.',
            workspace_mode=WorkspaceMode.GIT_WORKTREE,
            workspace_root=None,
            runtime_mode=RuntimeMode.PANE_BACKED,
            restore_default=RestoreMode.AUTO,
            permission_default=PermissionMode.MANUAL,
            queue_policy=QueuePolicy.SERIAL_PER_AGENT,
        )
    return ProjectConfig(
        version=2,
        default_agents=DEFAULT_DEFAULT_AGENTS,
        agents=agents,
        cmd_enabled=True,
    )


def render_default_project_config_text() -> str:
    config = build_default_project_config()
    return render_project_config_text(config)


def render_project_config_text(config: ProjectConfig) -> str:
    if _can_render_compact(config):
        return f'{config.layout_spec}\n'
    payload = {
        'version': config.version,
        'default_agents': list(config.default_agents),
        'cmd_enabled': bool(config.cmd_enabled),
        'layout': config.layout_spec,
        'agents': {name: _agent_spec_to_config_dict(spec) for name, spec in config.agents.items()},
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + '\n'


def _can_render_compact(config: ProjectConfig) -> bool:
    if not config.cmd_enabled:
        return False
    return all(_is_compact_agent_compatible(config.agents[name]) for name in config.default_agents)


def _is_compact_agent_compatible(spec: AgentSpec) -> bool:
    return (
        spec.target == '.'
        and spec.workspace_mode is WorkspaceMode.GIT_WORKTREE
        and spec.workspace_root is None
        and spec.runtime_mode is RuntimeMode.PANE_BACKED
        and spec.restore_default is RestoreMode.AUTO
        and spec.permission_default is PermissionMode.MANUAL
        and spec.queue_policy is QueuePolicy.SERIAL_PER_AGENT
        and not spec.startup_args
        and not spec.env
        and spec.provider_profile == ProviderProfileSpec()
        and spec.branch_template is None
        and not spec.labels
        and spec.description is None
        and not spec.watch_paths
    )


def _agent_spec_to_config_dict(spec: AgentSpec) -> dict[str, object]:
    payload: dict[str, object] = {
        'provider': spec.provider,
        'target': spec.target,
        'workspace_mode': spec.workspace_mode.value,
        'runtime_mode': spec.runtime_mode.value,
        'restore': spec.restore_default.value,
        'permission': spec.permission_default.value,
        'queue_policy': spec.queue_policy.value,
    }
    if spec.workspace_root is not None:
        payload['workspace_root'] = spec.workspace_root
    if spec.startup_args:
        payload['startup_args'] = list(spec.startup_args)
    if spec.env:
        payload['env'] = dict(spec.env)
    if spec.provider_profile != ProviderProfileSpec():
        payload['provider_profile'] = spec.provider_profile.to_record()
    if spec.branch_template is not None:
        payload['branch_template'] = spec.branch_template
    if spec.labels:
        payload['labels'] = list(spec.labels)
    if spec.description is not None:
        payload['description'] = spec.description
    if spec.watch_paths:
        payload['watch_paths'] = list(spec.watch_paths)
    return payload


__all__ = ['build_default_project_config', 'render_default_project_config_text', 'render_project_config_text']
