from __future__ import annotations

from typing import Iterable

from .nodes import LayoutLeaf, LayoutNode


def prune_layout(node: LayoutNode, *, include_names: Iterable[str]) -> LayoutNode | None:
    include = {str(name).strip() for name in include_names if str(name).strip()}
    if node.kind == 'leaf':
        assert node.leaf is not None
        if node.leaf.name in include:
            return node
        return None
    assert node.left is not None
    assert node.right is not None
    left = prune_layout(node.left, include_names=include)
    right = prune_layout(node.right, include_names=include)
    if left is None:
        return right
    if right is None:
        return left
    return LayoutNode(kind=node.kind, left=left, right=right)


def build_balanced_layout(
    agent_names: Iterable[str],
    *,
    providers_by_agent: dict[str, str] | None = None,
    workspace_modes_by_agent: dict[str, str] | None = None,
    cmd_enabled: bool = False,
) -> LayoutNode:
    ordered_agents = [str(name).strip() for name in agent_names if str(name).strip()]
    if not ordered_agents:
        raise ValueError('at least one agent is required for layout')
    leaves = layout_leaves(
        ordered_agents,
        providers_by_agent=dict(providers_by_agent or {}),
        workspace_modes_by_agent=dict(workspace_modes_by_agent or {}),
        cmd_enabled=cmd_enabled,
    )
    if len(leaves) == 1:
        return leaves[0]
    mid = (len(leaves) + 1) // 2
    left = stack_vertical(leaves[:mid])
    right = stack_vertical(leaves[mid:])
    if right is None:
        return left
    return LayoutNode(kind='horizontal', left=left, right=right)


def layout_leaves(
    ordered_agents: list[str],
    *,
    providers_by_agent: dict[str, str],
    workspace_modes_by_agent: dict[str, str],
    cmd_enabled: bool,
) -> list[LayoutNode]:
    leaves: list[LayoutNode] = []
    if cmd_enabled:
        leaves.append(LayoutNode(kind='leaf', leaf=LayoutLeaf(name='cmd')))
    for name in ordered_agents:
        leaves.append(
            LayoutNode(
                kind='leaf',
                leaf=LayoutLeaf(
                    name=name,
                    provider=(providers_by_agent.get(name) or None),
                    workspace_mode=(workspace_modes_by_agent.get(name) or None),
                ),
            )
        )
    return leaves


def stack_vertical(leaves: list[LayoutNode]) -> LayoutNode | None:
    if not leaves:
        return None
    node = leaves[0]
    for leaf in leaves[1:]:
        node = LayoutNode(kind='vertical', left=node, right=leaf)
    return node


__all__ = ['build_balanced_layout', 'prune_layout']
