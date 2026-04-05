from __future__ import annotations

from dataclasses import dataclass

from agents.models import ProjectConfig, ProjectLayoutPlan, build_project_layout_plan
from cli.context import CliContext
from terminal_runtime import TmuxBackend
from terminal_runtime.tmux_identity import apply_ccb_pane_identity


@dataclass(frozen=True)
class TmuxStartLayout:
    cmd_pane_id: str | None
    agent_panes: dict[str, str]


def prepare_tmux_start_layout(
    context: CliContext,
    *,
    config: ProjectConfig,
    targets: tuple[str, ...],
    tmux_backend=None,
    root_pane_id: str | None = None,
    layout_plan: ProjectLayoutPlan | None = None,
) -> TmuxStartLayout:
    if not targets:
        return TmuxStartLayout(cmd_pane_id=None, agent_panes={})

    backend = tmux_backend or TmuxBackend()
    resolved_root_pane_id = root_pane_id or backend.get_current_pane_id()
    resolved_layout_plan = layout_plan or build_project_layout_plan(
        config,
        target_agent_names=targets,
    )
    style_index_by_agent = {name: index for index, name in enumerate(resolved_layout_plan.target_agent_names)}

    agent_panes: dict[str, str] = {}

    def assign_leaf(item: str, pane_id: str) -> None:
        if item == 'cmd':
            _label_pane(
                backend,
                pane_id,
                title='cmd',
                agent_label='cmd',
                project_id=context.project.project_id,
                is_cmd=True,
            )
            return
        agent_panes[item] = pane_id
        _label_pane(
            backend,
            pane_id,
            title=item,
            agent_label=item,
            project_id=context.project.project_id,
            order_index=style_index_by_agent[item],
        )

    _materialize_layout(
        backend,
        parent_pane_id=resolved_root_pane_id,
        node=resolved_layout_plan.layout,
        cwd=str(context.project.project_root),
        assign_leaf=assign_leaf,
    )
    return TmuxStartLayout(
        cmd_pane_id=resolved_root_pane_id if resolved_layout_plan.cmd_enabled else None,
        agent_panes=agent_panes,
    )


def _materialize_layout(
    backend,
    *,
    parent_pane_id: str,
    node,
    cwd: str,
    assign_leaf,
) -> None:
    if node.kind == 'leaf':
        assert node.leaf is not None
        assign_leaf(node.leaf.name, parent_pane_id)
        return

    assert node.left is not None
    assert node.right is not None
    total = max(1, node.leaf_count)
    right_count = max(1, node.right.leaf_count)
    percent = max(1, min(99, round((right_count * 100) / total)))
    direction = 'right' if node.kind == 'horizontal' else 'bottom'
    new_pane_id = backend.create_pane('', cwd, direction=direction, percent=percent, parent_pane=parent_pane_id)
    _materialize_layout(
        backend,
        parent_pane_id=parent_pane_id,
        node=node.left,
        cwd=cwd,
        assign_leaf=assign_leaf,
    )
    _materialize_layout(
        backend,
        parent_pane_id=new_pane_id,
        node=node.right,
        cwd=cwd,
        assign_leaf=assign_leaf,
    )


def _label_pane(
    backend: TmuxBackend,
    pane_id: str,
    *,
    title: str,
    agent_label: str,
    project_id: str,
    order_index: int | None = None,
    is_cmd: bool = False,
) -> None:
    apply_ccb_pane_identity(
        backend,
        pane_id,
        title=title,
        agent_label=agent_label,
        project_id=project_id,
        order_index=order_index,
        is_cmd=is_cmd,
    )


__all__ = ['TmuxStartLayout', 'prepare_tmux_start_layout']
