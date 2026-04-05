from __future__ import annotations

import pytest

from agents.models import AgentSpec, PermissionMode, ProjectConfig, QueuePolicy, RestoreMode, RuntimeMode, WorkspaceMode
from agents.models import build_project_layout_plan


def _spec(name: str, provider: str) -> AgentSpec:
    return AgentSpec(
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


def _config(*, layout_spec: str, cmd_enabled: bool = True, agent_pairs: tuple[tuple[str, str], ...] | None = None) -> ProjectConfig:
    pairs = agent_pairs or (
        ('agent1', 'codex'),
        ('agent2', 'codex'),
        ('agent3', 'claude'),
        ('agent4', 'codex'),
        ('agent5', 'gemini'),
    )
    agents = {name: _spec(name, provider) for name, provider in pairs}
    return ProjectConfig(
        version=2,
        default_agents=tuple(name for name, _ in pairs),
        agents=agents,
        cmd_enabled=cmd_enabled,
        layout_spec=layout_spec,
    )


def test_build_project_layout_plan_preserves_three_column_layout_signature() -> None:
    config = _config(
        layout_spec='cmd, agent1:codex; agent2:codex, agent3:claude; agent4:codex, agent5:gemini'
    )

    plan = build_project_layout_plan(config)

    assert plan.target_agent_names == ('agent1', 'agent2', 'agent3', 'agent4', 'agent5')
    assert plan.visible_leaf_names == ('cmd', 'agent1', 'agent2', 'agent3', 'agent4', 'agent5')
    assert plan.signature == 'cmd, agent1:codex; agent2:codex, agent3:claude; agent4:codex, agent5:gemini'


def test_build_project_layout_plan_prunes_subset_without_reordering_columns() -> None:
    config = _config(
        layout_spec='cmd, agent1:codex; agent2:codex, agent3:claude; agent4:codex, agent5:gemini'
    )

    plan = build_project_layout_plan(config, requested_agents=('agent2', 'agent5'))

    assert plan.target_agent_names == ('agent2', 'agent5')
    assert plan.visible_leaf_names == ('cmd', 'agent2', 'agent5')
    assert plan.signature == 'cmd; agent2:codex; agent5:gemini'


def test_build_project_layout_plan_rejects_unknown_requested_agent() -> None:
    config = _config(
        layout_spec='cmd; agent1:codex',
        agent_pairs=(('agent1', 'codex'),),
    )

    with pytest.raises(Exception, match='unknown agent'):
        build_project_layout_plan(config, requested_agents=('missing',))
