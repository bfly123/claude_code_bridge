from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectNamespace:
    project_id: str
    namespace_epoch: int
    tmux_socket_path: str
    tmux_session_name: str
    layout_version: int
    layout_signature: str | None
    control_window_name: str | None
    control_window_id: str | None
    workspace_window_name: str | None
    workspace_window_id: str | None
    workspace_epoch: int
    ui_attachable: bool
    created_this_call: bool = False
    workspace_recreated_this_call: bool = False

    @classmethod
    def from_state(cls, state) -> ProjectNamespace:
        return cls(
            project_id=state.project_id,
            namespace_epoch=state.namespace_epoch,
            tmux_socket_path=state.tmux_socket_path,
            tmux_session_name=state.tmux_session_name,
            layout_version=state.layout_version,
            layout_signature=state.layout_signature,
            control_window_name=state.control_window_name,
            control_window_id=state.control_window_id,
            workspace_window_name=state.workspace_window_name,
            workspace_window_id=state.workspace_window_id,
            workspace_epoch=state.workspace_epoch,
            ui_attachable=state.ui_attachable,
            created_this_call=False,
            workspace_recreated_this_call=False,
        )


@dataclass(frozen=True)
class ProjectNamespaceDestroySummary:
    project_id: str
    namespace_epoch: int | None
    tmux_socket_path: str
    tmux_session_name: str
    destroyed: bool
    reason: str


__all__ = ['ProjectNamespace', 'ProjectNamespaceDestroySummary']
