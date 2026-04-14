from __future__ import annotations

from agents.models import (
    AgentSpec,
    PermissionMode,
    ProjectConfig,
    QueuePolicy,
    RestoreMode,
    RuntimeMode,
    WorkspaceMode,
)

from ..common import DEFAULT_DEFAULT_AGENTS

DEFAULT_AGENT_PROVIDERS = (
    ('agent1', 'codex'),
    ('agent2', 'codex'),
    ('agent3', 'claude'),
)


def build_default_project_config() -> ProjectConfig:
    agents = {
        name: build_default_agent_spec(name=name, provider=provider)
        for name, provider in DEFAULT_AGENT_PROVIDERS
    }
    return ProjectConfig(
        version=2,
        default_agents=DEFAULT_DEFAULT_AGENTS,
        agents=agents,
        cmd_enabled=True,
    )


def build_default_agent_spec(*, name: str, provider: str) -> AgentSpec:
    return AgentSpec(
        name=name,
        provider=provider,
        target='.',
        workspace_mode=WorkspaceMode.INPLACE,
        workspace_root=None,
        runtime_mode=RuntimeMode.PANE_BACKED,
        restore_default=RestoreMode.AUTO,
        permission_default=PermissionMode.MANUAL,
        queue_policy=QueuePolicy.SERIAL_PER_AGENT,
    )


__all__ = ['DEFAULT_AGENT_PROVIDERS', 'build_default_agent_spec', 'build_default_project_config']
