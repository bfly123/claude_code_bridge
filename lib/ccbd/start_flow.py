from __future__ import annotations

from pathlib import Path

from agents.models import build_project_layout_plan
from ccbd.models import CcbdStartupAgentResult
from ccbd.start_flow_runtime import StartFlowDeps, StartFlowSummary, run_start_flow as run_start_flow_impl
from ccbd.start_preparation import prepare_start_agents
from ccbd.start_runtime.agent_runtime import start_agent_runtime as start_agent_runtime_impl
from ccbd.start_runtime.binding import declared_binding_tmux_socket_path as declared_binding_tmux_socket_path_impl
from ccbd.start_runtime.binding import launch_binding_hint as launch_binding_hint_impl
from ccbd.start_runtime.binding import relabel_project_namespace_pane as relabel_project_namespace_pane_impl
from ccbd.start_runtime.binding import usable_agent_only_project_binding as usable_agent_only_project_binding_impl
from ccbd.start_runtime.binding import usable_project_binding as usable_project_binding_impl
from ccbd.start_runtime.binding import usable_project_namespace_binding as usable_project_namespace_binding_impl
from ccbd.start_runtime.cleanup import cleanup_start_tmux_orphans as cleanup_start_tmux_orphans_impl
from ccbd.start_runtime.layout import bootstrap_project_namespace_cmd_pane as bootstrap_project_namespace_cmd_pane_impl
from ccbd.start_runtime.layout import cmd_bootstrap_command as cmd_bootstrap_command_impl
from ccbd.start_runtime.layout import inside_tmux as inside_tmux_impl
from ccbd.start_runtime.layout import prepare_start_layout as prepare_start_layout_impl
from ccbd.start_runtime.layout import session_root_pane as session_root_pane_impl
from ccbd.start_runtime.restore import build_restore_state as build_restore_state_impl
from ccbd.system import utc_now
from ccbd.services.project_namespace_pane import inspect_project_namespace_pane, same_tmux_socket_path
from cli.services.runtime_launch import ensure_agent_runtime
from cli.services.tmux_cleanup_history import TmuxCleanupHistoryStore
from cli.services.tmux_project_cleanup import ProjectTmuxCleanupSummary, cleanup_project_tmux_orphans_by_socket
from cli.services.tmux_start_layout import prepare_tmux_start_layout
from cli.services.tmux_ui import set_tmux_ui_active
from provider_core.session_binding_evidence import resolve_agent_binding
from terminal_runtime import TmuxBackend
from terminal_runtime.tmux_identity import apply_ccb_pane_identity


def _deps() -> StartFlowDeps:
    return StartFlowDeps(
        build_project_layout_plan_fn=build_project_layout_plan,
        prepare_start_agents_fn=prepare_start_agents,
        start_agent_runtime_impl=start_agent_runtime_impl,
        prepare_start_layout_impl=prepare_start_layout_impl,
        session_root_pane_impl=session_root_pane_impl,
        inside_tmux_impl=inside_tmux_impl,
        usable_project_namespace_binding_impl=usable_project_namespace_binding_impl,
        usable_project_binding_impl=usable_project_binding_impl,
        usable_agent_only_project_binding_impl=usable_agent_only_project_binding_impl,
        declared_binding_tmux_socket_path_impl=declared_binding_tmux_socket_path_impl,
        launch_binding_hint_impl=launch_binding_hint_impl,
        relabel_project_namespace_pane_impl=relabel_project_namespace_pane_impl,
        bootstrap_project_namespace_cmd_pane_impl=bootstrap_project_namespace_cmd_pane_impl,
        cmd_bootstrap_command_impl=cmd_bootstrap_command_impl,
        build_restore_state_impl=build_restore_state_impl,
        cleanup_start_tmux_orphans_impl=cleanup_start_tmux_orphans_impl,
        set_tmux_ui_active_fn=set_tmux_ui_active,
        prepare_tmux_start_layout_fn=prepare_tmux_start_layout,
        ensure_agent_runtime_fn=ensure_agent_runtime,
        resolve_agent_binding_fn=resolve_agent_binding,
        cleanup_project_tmux_orphans_by_socket_fn=cleanup_project_tmux_orphans_by_socket,
        tmux_cleanup_history_store_cls=TmuxCleanupHistoryStore,
        tmux_backend_cls=TmuxBackend,
        inspect_project_namespace_pane_fn=inspect_project_namespace_pane,
        same_tmux_socket_path_fn=same_tmux_socket_path,
        apply_ccb_pane_identity_fn=apply_ccb_pane_identity,
    )


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
    cleanup_tmux_orphans: bool = True,
    interactive_tmux_layout: bool = True,
    tmux_socket_path: str | None = None,
    tmux_session_name: str | None = None,
    tmux_workspace_window_name: str | None = None,
    namespace_epoch: int | None = None,
    workspace_window_id: str | None = None,
    workspace_epoch: int | None = None,
    fresh_namespace: bool = False,
    fresh_workspace: bool = False,
    clock=utc_now,
) -> StartFlowSummary:
    return run_start_flow_impl(
        project_root=project_root,
        project_id=project_id,
        paths=paths,
        config=config,
        runtime_service=runtime_service,
        requested_agents=requested_agents,
        restore=restore,
        auto_permission=auto_permission,
        cleanup_tmux_orphans=cleanup_tmux_orphans,
        interactive_tmux_layout=interactive_tmux_layout,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        tmux_workspace_window_name=tmux_workspace_window_name,
        namespace_epoch=namespace_epoch,
        workspace_window_id=workspace_window_id,
        workspace_epoch=workspace_epoch,
        fresh_namespace=fresh_namespace,
        fresh_workspace=fresh_workspace,
        clock=clock,
        deps=_deps(),
    )


__all__ = ['CcbdStartupAgentResult', 'ProjectTmuxCleanupSummary', 'StartFlowSummary', 'run_start_flow']
