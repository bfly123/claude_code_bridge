from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StartFlowDeps:
    build_project_layout_plan_fn: object
    prepare_start_agents_fn: object
    start_agent_runtime_impl: object
    prepare_start_layout_impl: object
    session_root_pane_impl: object
    inside_tmux_impl: object
    usable_project_namespace_binding_impl: object
    usable_project_binding_impl: object
    usable_agent_only_project_binding_impl: object
    declared_binding_tmux_socket_path_impl: object
    launch_binding_hint_impl: object
    relabel_project_namespace_pane_impl: object
    bootstrap_project_namespace_cmd_pane_impl: object
    cmd_bootstrap_command_impl: object
    build_restore_state_impl: object
    cleanup_start_tmux_orphans_impl: object
    set_tmux_ui_active_fn: object
    prepare_tmux_start_layout_fn: object
    ensure_agent_runtime_fn: object
    resolve_agent_binding_fn: object
    cleanup_project_tmux_orphans_by_socket_fn: object
    tmux_cleanup_history_store_cls: object
    tmux_backend_cls: object
    inspect_project_namespace_pane_fn: object
    same_tmux_socket_path_fn: object
    apply_ccb_pane_identity_fn: object


__all__ = ['StartFlowDeps']
