from __future__ import annotations

from pathlib import Path

from cli.context import CliContext
from cli.models import ParsedStartCommand
from cli.services.tmux_start_layout import TmuxStartLayout
from project.resolver import ProjectContext

from .binding import bootstrap_project_namespace_cmd_pane, launch_binding_hint, relabel_project_namespace_pane, usable_project_binding
from .layout import cleanup_start_tmux_orphans, prepare_start_layout, session_root_pane
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
    namespace_epoch: int | None,
    fresh_namespace: bool,
    clock,
    deps,
) -> StartFlowSummary:
    command, context = _build_start_context(
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
    tmux_backend, root_pane_id = _tmux_namespace_runtime(
        deps,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
    )

    _record_namespace_action(
        actions_taken,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        namespace_epoch=namespace_epoch,
    )

    prepared_agents = _prepare_agents(
        deps,
        targets=targets,
        config=config,
        paths=paths,
        context=context,
        project_root=project_root,
        project_id=project_id,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
    )
    prepared_by_agent = {item.agent_name: item for item in prepared_agents}

    tmux_layout = _tmux_layout_for_start(
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
    project_socket_active_panes, cmd_pane_id = _project_socket_active_panes(
        tmux_layout=tmux_layout,
        tmux_socket_path=tmux_socket_path,
        config=config,
        root_pane_id=root_pane_id,
    )
    _bootstrap_cmd_pane_if_needed(
        deps,
        fresh_namespace=fresh_namespace,
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
            ensure_agent_runtime_fn=deps.ensure_agent_runtime_fn,
            launch_binding_hint_fn=lambda **kwargs: launch_binding_hint(deps, **kwargs),
            relabel_project_namespace_pane_fn=lambda **kwargs: relabel_project_namespace_pane(deps, **kwargs),
            same_tmux_socket_path_fn=deps.same_tmux_socket_path_fn,
        )
        actions_taken.extend(execution.actions_taken)
        _record_active_panes(
            active_panes_by_socket,
            project_socket_active_panes,
            execution=execution,
        )
        agent_results.append(execution.agent_result)

    cleanup_summaries = _cleanup_tmux_orphans_if_needed(
        deps,
        cleanup_tmux_orphans=cleanup_tmux_orphans,
        project_id=project_id,
        paths=paths,
        active_panes_by_socket=active_panes_by_socket,
        project_socket_active_panes=project_socket_active_panes,
        tmux_socket_path=tmux_socket_path,
        clock=clock,
        actions_taken=actions_taken,
    )
    return StartFlowSummary(
        project_root=str(project_root),
        project_id=project_id,
        started=targets,
        socket_path=str(paths.ccbd_socket_path),
        cleanup_summaries=tuple(cleanup_summaries),
        actions_taken=tuple(actions_taken),
        agent_results=tuple(agent_results),
    )


def _build_start_context(
    *,
    project_root: Path,
    project_id: str,
    paths,
    requested_agents: tuple[str, ...],
    restore: bool,
    auto_permission: bool,
) -> tuple[ParsedStartCommand, CliContext]:
    command = ParsedStartCommand(
        project=str(project_root),
        agent_names=tuple(requested_agents),
        restore=bool(restore),
        auto_permission=bool(auto_permission),
    )
    context = CliContext(
        command=command,
        cwd=project_root,
        project=ProjectContext(
            cwd=project_root,
            project_root=project_root,
            config_dir=paths.ccb_dir,
            project_id=project_id,
            source='ccbd',
        ),
        paths=paths,
    )
    return command, context


def _tmux_namespace_runtime(deps, *, tmux_socket_path: str | None, tmux_session_name: str | None):
    tmux_backend = deps.tmux_backend_cls(socket_path=tmux_socket_path) if tmux_socket_path is not None else None
    if tmux_backend is None or not tmux_session_name:
        return tmux_backend, None
    return tmux_backend, session_root_pane(deps, tmux_backend, tmux_session_name)


def _record_namespace_action(
    actions_taken: list[str],
    *,
    tmux_socket_path: str | None,
    tmux_session_name: str | None,
    namespace_epoch: int | None,
) -> None:
    if tmux_socket_path is None or tmux_session_name is None:
        return
    actions_taken.append(
        'ensure_namespace:'
        f'epoch={namespace_epoch if namespace_epoch is not None else "unknown"},'
        f'session={tmux_session_name}'
    )


def _prepare_agents(
    deps,
    *,
    targets,
    config,
    paths,
    context,
    project_root: Path,
    project_id: str,
    tmux_socket_path: str | None,
    tmux_session_name: str | None,
):
    return deps.prepare_start_agents_fn(
        targets=targets,
        config=config,
        paths=paths,
        context=context,
        project_root=project_root,
        project_id=project_id,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        resolve_agent_binding_fn=deps.resolve_agent_binding_fn,
        project_binding_filter_fn=lambda binding, **kwargs: usable_project_binding(deps, binding, **kwargs),
        restore_state_builder=deps.build_restore_state_impl,
    )


def _tmux_layout_for_start(
    deps,
    context,
    *,
    config,
    prepared_agents,
    interactive_tmux_layout: bool,
    tmux_backend,
    root_pane_id: str | None,
    actions_taken: list[str],
) -> TmuxStartLayout:
    if not interactive_tmux_layout:
        return TmuxStartLayout(cmd_pane_id=None, agent_panes={})
    deps.set_tmux_ui_active_fn(True)
    launch_targets = tuple(item.agent_name for item in prepared_agents if item.binding is None)
    if launch_targets:
        actions_taken.append(f'prepare_tmux_layout:{",".join(launch_targets)}')
    return prepare_start_layout(
        deps,
        context,
        config=config,
        targets=launch_targets,
        layout_plan=(
            deps.build_project_layout_plan_fn(config, target_agent_names=launch_targets)
            if launch_targets
            else None
        ),
        tmux_backend=tmux_backend,
        root_pane_id=root_pane_id,
    )


def _project_socket_active_panes(
    *,
    tmux_layout: TmuxStartLayout,
    tmux_socket_path: str | None,
    config,
    root_pane_id: str | None,
) -> tuple[list[str], str | None]:
    project_socket_active_panes: list[str] = []
    cmd_pane_id = tmux_layout.cmd_pane_id
    if cmd_pane_id is None and tmux_socket_path is not None and bool(getattr(config, 'cmd_enabled', False)):
        cmd_pane_id = root_pane_id
    if cmd_pane_id and tmux_socket_path is not None:
        project_socket_active_panes.append(cmd_pane_id)
    return project_socket_active_panes, cmd_pane_id


def _bootstrap_cmd_pane_if_needed(
    deps,
    *,
    fresh_namespace: bool,
    cmd_pane_id: str | None,
    project_root: Path,
    project_id: str,
    tmux_socket_path: str | None,
    namespace_epoch: int | None,
    actions_taken: list[str],
) -> None:
    if not fresh_namespace or cmd_pane_id is None:
        return
    bootstrapped_cmd_pane = bootstrap_project_namespace_cmd_pane(
        deps,
        pane_id=cmd_pane_id,
        project_root=project_root,
        project_id=project_id,
        tmux_socket_path=tmux_socket_path,
        namespace_epoch=namespace_epoch,
    )
    if bootstrapped_cmd_pane is not None:
        actions_taken.append(f'bootstrap_cmd_pane:{bootstrapped_cmd_pane}')


def _record_active_panes(
    active_panes_by_socket: dict[str | None, list[str]],
    project_socket_active_panes: list[str],
    *,
    execution,
) -> None:
    if execution.runtime_pane_id is not None:
        active_panes_by_socket.setdefault(execution.socket_name, []).append(execution.runtime_pane_id)
    if execution.project_socket_active_pane_id is not None:
        project_socket_active_panes.append(execution.project_socket_active_pane_id)


def _cleanup_tmux_orphans_if_needed(
    deps,
    *,
    cleanup_tmux_orphans: bool,
    project_id: str,
    paths,
    active_panes_by_socket: dict[str | None, list[str]],
    project_socket_active_panes: list[str],
    tmux_socket_path: str | None,
    clock,
    actions_taken: list[str],
) -> tuple[object, ...]:
    if not cleanup_tmux_orphans:
        return ()
    cleanup_summaries = cleanup_start_tmux_orphans(
        deps,
        project_id=project_id,
        paths=paths,
        active_panes_by_socket=active_panes_by_socket,
        project_socket_active_panes=project_socket_active_panes,
        tmux_socket_path=tmux_socket_path,
        clock=clock,
    )
    total_killed = sum(len(item.killed_panes) for item in cleanup_summaries)
    actions_taken.append(f'cleanup_tmux_orphans:killed={total_killed}')
    return tuple(cleanup_summaries)


__all__ = ['run_start_flow']
