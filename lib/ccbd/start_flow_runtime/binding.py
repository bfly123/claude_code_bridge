from __future__ import annotations

from pathlib import Path


def usable_project_binding(
    deps,
    binding,
    *,
    cmd_enabled: bool,
    tmux_socket_path: str,
    tmux_session_name: str | None,
    workspace_window_id: str | None,
    agent_name: str,
    project_id: str,
):
    return deps.usable_project_binding_impl(
        binding,
        cmd_enabled=cmd_enabled,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        workspace_window_id=workspace_window_id,
        agent_name=agent_name,
        project_id=project_id,
        tmux_backend_factory=deps.tmux_backend_cls,
        inspect_project_namespace_pane_fn=deps.inspect_project_namespace_pane_fn,
        same_tmux_socket_path_fn=deps.same_tmux_socket_path_fn,
    )


def launch_binding_hint(
    deps,
    *,
    binding,
    raw_binding,
    stale_binding: bool,
    assigned_pane_id: str | None,
    tmux_socket_path: str | None,
):
    return deps.launch_binding_hint_impl(
        binding=binding,
        raw_binding=raw_binding,
        stale_binding=stale_binding,
        assigned_pane_id=assigned_pane_id,
        tmux_socket_path=tmux_socket_path,
        same_tmux_socket_path_fn=deps.same_tmux_socket_path_fn,
    )


def relabel_project_namespace_pane(
    deps,
    *,
    binding,
    agent_name: str,
    project_id: str,
    style_index: int,
    tmux_socket_path: str | None,
    namespace_epoch: int | None,
) -> str | None:
    return deps.relabel_project_namespace_pane_impl(
        binding=binding,
        agent_name=agent_name,
        project_id=project_id,
        style_index=style_index,
        tmux_socket_path=tmux_socket_path,
        namespace_epoch=namespace_epoch,
        tmux_backend_factory=deps.tmux_backend_cls,
        same_tmux_socket_path_fn=deps.same_tmux_socket_path_fn,
        apply_ccb_pane_identity_fn=deps.apply_ccb_pane_identity_fn,
    )


def bootstrap_project_namespace_cmd_pane(
    deps,
    *,
    pane_id: str,
    project_root: Path,
    project_id: str,
    tmux_socket_path: str | None,
    namespace_epoch: int | None,
) -> str | None:
    return deps.bootstrap_project_namespace_cmd_pane_impl(
        pane_id=pane_id,
        project_root=project_root,
        project_id=project_id,
        tmux_socket_path=tmux_socket_path,
        namespace_epoch=namespace_epoch,
        tmux_backend_factory=deps.tmux_backend_cls,
        apply_ccb_pane_identity_fn=deps.apply_ccb_pane_identity_fn,
        cmd_bootstrap_command_fn=deps.cmd_bootstrap_command_impl,
    )


__all__ = [
    'bootstrap_project_namespace_cmd_pane',
    'launch_binding_hint',
    'relabel_project_namespace_pane',
    'usable_project_binding',
]
