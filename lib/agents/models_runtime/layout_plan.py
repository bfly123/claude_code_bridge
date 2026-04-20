from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .config import ProjectConfig
from .layout import LayoutNode, parse_layout_spec, prune_layout
from .names import AgentValidationError, normalize_agent_name


@dataclass(frozen=True)
class ProjectLayoutPlan:
    target_agent_names: tuple[str, ...]
    visible_leaf_names: tuple[str, ...]
    layout: LayoutNode
    signature: str
    cmd_enabled: bool


def select_project_layout_targets(config: ProjectConfig, *, requested_agents: Iterable[str] = ()) -> tuple[str, ...]:
    requested = tuple(str(item or '').strip() for item in requested_agents)
    if not requested:
        return tuple(config.default_agents)
    selected: list[str] = []
    known_agents = set(config.agents)
    for item in requested:
        lowered = normalize_agent_name(item)
        if lowered not in known_agents:
            raise AgentValidationError(f'unknown agent: {item}')
        if lowered not in selected:
            selected.append(lowered)
    return tuple(selected)


def build_project_layout_plan(
    config: ProjectConfig,
    *,
    requested_agents: Iterable[str] = (),
    target_agent_names: Iterable[str] | None = None,
) -> ProjectLayoutPlan:
    targets = (
        tuple(normalize_agent_name(item) for item in target_agent_names)
        if target_agent_names is not None
        else select_project_layout_targets(config, requested_agents=requested_agents)
    )
    include_names: tuple[str, ...] = (('cmd',) if config.cmd_enabled else ()) + targets
    pruned_layout = prune_layout(
        parse_layout_spec(str(config.layout_spec or '')),
        include_names=include_names,
    )
    if pruned_layout is None:
        raise AgentValidationError('layout_spec does not include any visible panes for the requested start')
    visible_leaf_names = tuple(leaf.name for leaf in pruned_layout.iter_leaves())
    if config.cmd_enabled and visible_leaf_names[:1] != ('cmd',):
        raise AgentValidationError('pruned layout must retain cmd as the first visible pane')
    return ProjectLayoutPlan(
        target_agent_names=targets,
        visible_leaf_names=visible_leaf_names,
        layout=pruned_layout,
        signature=pruned_layout.render(),
        cmd_enabled=bool(config.cmd_enabled),
    )


def project_layout_signature(
    config: ProjectConfig,
    *,
    requested_agents: Iterable[str] = (),
    target_agent_names: Iterable[str] | None = None,
) -> str:
    return build_project_layout_plan(
        config,
        requested_agents=requested_agents,
        target_agent_names=target_agent_names,
    ).signature


__all__ = [
    'ProjectLayoutPlan',
    'build_project_layout_plan',
    'project_layout_signature',
    'select_project_layout_targets',
]
