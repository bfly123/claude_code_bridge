from __future__ import annotations

from pathlib import Path

from .binding import launch_binding_hint, relabel_project_namespace_pane
from .service_agents import prepare_agents
from .service_context import build_start_context, record_namespace_action
from .service_tmux import (
    bootstrap_cmd_pane_if_needed,
    cleanup_tmux_orphans_if_needed,
    project_socket_active_panes,
    record_active_panes,
    tmux_layout_for_start,
    tmux_namespace_runtime,
)
from .summary import StartFlowSummary


def run_start_flow(
    *,
    project_root: Path,
    project_id: str,
    paths,
    config,
    runtime_service,
    requested_agents: tuple[str, ...],
    restore: bool,
    auto_permission: bool,
    cleanup_tmux_orphans: bool,
    interactive_tmux_layout: bool,
    tmux_socket_path: str | None,
    tmux_session_name: str | None,
    tmux_workspace_window_name: str | None,
    namespace_epoch: int | None,
    workspace_window_id: str | None,
    workspace_epoch: int | None,
    fresh_namespace: bool,
    fresh_workspace: bool,
    clock,
    deps,
) -> StartFlowSummary:
    command, context = build_start_context(
        project_root=project_root,
        project_id=project_id,
        paths=paths,
        requested_agents=requested_agents,
        restore=restore,
        auto_permission=auto_permission,
    )
    layout_plan = deps.build_project_layout_plan_fn(config, requested_agents=command.agent_names)
    targets = layout_plan.target_agent_names
    actions_taken: list[str] = []
    agent_results: list[object] = []
    tmux_backend, root_pane_id = tmux_namespace_runtime(
        deps,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        tmux_workspace_window_name=tmux_workspace_window_name,
    )

    record_namespace_action(
        actions_taken,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        namespace_epoch=namespace_epoch,
    )

    prepared_agents = prepare_agents(
        deps,
        targets=targets,
        config=config,
        paths=paths,
        context=context,
        project_root=project_root,
        project_id=project_id,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        workspace_window_id=workspace_window_id,
    )
    prepared_by_agent = {item.agent_name: item for item in prepared_agents}

    tmux_layout = tmux_layout_for_start(
        deps,
        context,
        config=config,
        prepared_agents=prepared_agents,
        interactive_tmux_layout=interactive_tmux_layout,
        tmux_backend=tmux_backend,
        root_pane_id=root_pane_id,
        actions_taken=actions_taken,
    )

    active_panes_by_socket: dict[str | None, list[str]] = {}
    active_project_panes, cmd_pane_id = project_socket_active_panes(
        tmux_layout=tmux_layout,
        tmux_socket_path=tmux_socket_path,
        config=config,
        root_pane_id=root_pane_id,
    )
    bootstrap_cmd_pane_if_needed(
        deps,
        fresh_namespace=(fresh_namespace or fresh_workspace),
        cmd_pane_id=cmd_pane_id,
        project_root=project_root,
        project_id=project_id,
        tmux_socket_path=tmux_socket_path,
        namespace_epoch=namespace_epoch,
        actions_taken=actions_taken,
    )

    for style_index, agent_name in enumerate(targets):
        prepared = prepared_by_agent[agent_name]
        execution = deps.start_agent_runtime_impl(
            context=context,
            command=command,
            runtime_service=runtime_service,
            agent_name=agent_name,
            spec=prepared.spec,
            plan=prepared.plan,
            binding=prepared.binding,
            raw_binding=prepared.raw_binding,
            stale_binding=prepared.stale_binding,
            assigned_pane_id=tmux_layout.agent_panes.get(agent_name),
            style_index=style_index,
            project_id=project_id,
            tmux_socket_path=tmux_socket_path,
            namespace_epoch=namespace_epoch,
            workspace_window_id=workspace_window_id,
            workspace_epoch=workspace_epoch,
            ensure_agent_runtime_fn=deps.ensure_agent_runtime_fn,
            launch_binding_hint_fn=lambda **kwargs: launch_binding_hint(deps, **kwargs),
            relabel_project_namespace_pane_fn=lambda **kwargs: relabel_project_namespace_pane(deps, **kwargs),
            same_tmux_socket_path_fn=deps.same_tmux_socket_path_fn,
        )
        actions_taken.extend(execution.actions_taken)
        record_active_panes(
            active_panes_by_socket,
            active_project_panes,
            execution=execution,
        )
        agent_results.append(execution.agent_result)

    cleanup_summaries = cleanup_tmux_orphans_if_needed(
        deps,
        cleanup_tmux_orphans=cleanup_tmux_orphans,
        project_id=project_id,
        paths=paths,
        active_panes_by_socket=active_panes_by_socket,
        project_socket_active_panes=active_project_panes,
        tmux_socket_path=tmux_socket_path,
        clock=clock,
        actions_taken=actions_taken,
    )
    return StartFlowSummary(
        project_root=str(project_root),
        project_id=project_id,
        started=targets,
        socket_path=str(paths.ccbd_ipc_ref),
        cleanup_summaries=tuple(cleanup_summaries),
        actions_taken=tuple(actions_taken),
        agent_results=tuple(agent_results),
    )


__all__ = ['run_start_flow']
