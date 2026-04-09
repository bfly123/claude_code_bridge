from __future__ import annotations

from cli.services.tmux_ui import apply_project_tmux_ui
from terminal_runtime.tmux_identity import apply_ccb_pane_identity

from .backend import create_session, ensure_window, prepare_server, session_window_target, window_root_pane


def prepare_namespace_root_pane(
    controller,
    context,
    *,
    epoch: int,
) -> None:
    prepare_server(context.backend)
    if not context.session_is_alive:
        create_session(
            context.backend,
            session_name=context.desired_session_name,
            project_root=controller._layout.project_root,
            window_name=context.desired_control_window_name,
        )
    ensure_window(
        context.backend,
        session_name=context.desired_session_name,
        window_name=context.desired_control_window_name,
        project_root=controller._layout.project_root,
        select=False,
    )
    ensure_window(
        context.backend,
        session_name=context.desired_session_name,
        window_name=context.desired_workspace_window_name,
        project_root=controller._layout.project_root,
        select=True,
    )
    root_pane = window_root_pane(
        context.backend,
        target_window=session_window_target(
            context.desired_session_name,
            context.desired_workspace_window_name,
        ),
    )
    apply_namespace_identity(
        controller,
        backend=context.backend,
        pane_id=root_pane,
        namespace_epoch=epoch,
        tmux_socket_path=context.desired_socket_path,
        tmux_session_name=context.desired_session_name,
    )


def apply_namespace_identity(
    controller,
    *,
    backend,
    pane_id: str,
    namespace_epoch: int,
    tmux_socket_path: str,
    tmux_session_name: str,
) -> None:
    apply_ccb_pane_identity(
        backend,
        pane_id,
        title='cmd',
        agent_label='cmd',
        project_id=controller._project_id,
        is_cmd=True,
        slot_key='cmd',
        namespace_epoch=namespace_epoch,
        managed_by='ccbd',
    )
    apply_project_tmux_ui(
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        backend=backend,
    )


__all__ = ['apply_namespace_identity', 'prepare_namespace_root_pane']
