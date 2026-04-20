from __future__ import annotations

from .validation_context import build_binding_validation_context
from .validation_rules import (
    usable_agent_only_project_binding_for_context,
    usable_project_namespace_binding_for_context,
)


def usable_project_namespace_binding(
    binding,
    *,
    tmux_socket_path: str,
    tmux_session_name: str | None,
    workspace_window_id: str | None,
    agent_name: str,
    project_id: str,
    tmux_backend_factory,
    inspect_project_namespace_pane_fn,
    same_tmux_socket_path_fn,
) -> object | None:
    context = build_binding_validation_context(
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        workspace_window_id=workspace_window_id,
        agent_name=agent_name,
        project_id=project_id,
        tmux_backend_factory=tmux_backend_factory,
        inspect_project_namespace_pane_fn=inspect_project_namespace_pane_fn,
        same_tmux_socket_path_fn=same_tmux_socket_path_fn,
    )
    return usable_project_namespace_binding_for_context(binding, context=context)


def usable_project_binding(
    binding,
    *,
    cmd_enabled: bool,
    tmux_socket_path: str,
    tmux_session_name: str | None,
    workspace_window_id: str | None,
    agent_name: str,
    project_id: str,
    tmux_backend_factory,
    inspect_project_namespace_pane_fn,
    same_tmux_socket_path_fn,
):
    context = build_binding_validation_context(
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        workspace_window_id=workspace_window_id,
        agent_name=agent_name,
        project_id=project_id,
        tmux_backend_factory=tmux_backend_factory,
        inspect_project_namespace_pane_fn=inspect_project_namespace_pane_fn,
        same_tmux_socket_path_fn=same_tmux_socket_path_fn,
    )
    if cmd_enabled:
        return usable_project_namespace_binding_for_context(binding, context=context)
    return usable_agent_only_project_binding_for_context(binding, context=context)


def usable_agent_only_project_binding(
    binding,
    *,
    tmux_socket_path: str,
    tmux_session_name: str | None,
    workspace_window_id: str | None,
    agent_name: str,
    project_id: str,
    tmux_backend_factory,
    inspect_project_namespace_pane_fn,
    same_tmux_socket_path_fn,
):
    context = build_binding_validation_context(
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        workspace_window_id=workspace_window_id,
        agent_name=agent_name,
        project_id=project_id,
        tmux_backend_factory=tmux_backend_factory,
        inspect_project_namespace_pane_fn=inspect_project_namespace_pane_fn,
        same_tmux_socket_path_fn=same_tmux_socket_path_fn,
    )
    return usable_agent_only_project_binding_for_context(binding, context=context)


__all__ = [
    "usable_agent_only_project_binding",
    "usable_project_binding",
    "usable_project_namespace_binding",
]
