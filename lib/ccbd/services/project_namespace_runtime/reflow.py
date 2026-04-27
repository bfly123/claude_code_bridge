from __future__ import annotations

from .backend import (
    create_window,
    ensure_window,
    find_window,
    kill_window,
    rename_window,
    select_window,
    session_window_target,
    window_root_pane,
)
from .ensure_context import load_namespace_context, refresh_session_liveness
from .ensure_identity import apply_namespace_identity
from .models import ProjectNamespace
from .records import build_active_state, namespace_from_state
from ..project_namespace_state import ProjectNamespaceEvent


def reflow_project_workspace(
    controller,
    *,
    layout_signature: str | None = None,
    reason: str | None = None,
    session_probe_timeout_s: float | None = None,
) -> ProjectNamespace:
    controller._layout.ccbd_dir.mkdir(parents=True, exist_ok=True)
    context = load_namespace_context(
        controller,
        layout_signature=layout_signature,
        recreate_reason=reason,
    )
    context = refresh_session_liveness(
        controller,
        context,
        timeout_s=session_probe_timeout_s,
    )
    current = context.current
    if current is None or not context.session_is_alive:
        return controller.ensure(
            layout_signature=layout_signature,
            force_recreate=False,
            recreate_reason=reason,
        )

    ensure_window(
        context.backend,
        session_name=context.desired_session_name,
        window_name=context.desired_control_window_name,
        project_root=controller._layout.project_root,
        select=False,
    )
    next_workspace_epoch = max(1, int(current.workspace_epoch)) + 1
    desired_workspace_name = context.desired_workspace_window_name
    temporary_workspace_name = f'{desired_workspace_name}.__reflow__.{next_workspace_epoch}'
    temporary_workspace = create_window(
        context.backend,
        session_name=context.desired_session_name,
        window_name=temporary_workspace_name,
        project_root=controller._layout.project_root,
        select=True,
    )
    root_pane = window_root_pane(
        context.backend,
        target_window=session_window_target(
            context.desired_session_name,
            temporary_workspace.window_id or temporary_workspace.window_name,
        ),
    )
    apply_namespace_identity(
        controller,
        backend=context.backend,
        pane_id=root_pane,
        namespace_epoch=current.namespace_epoch,
        tmux_socket_path=context.desired_socket_path,
        tmux_session_name=context.desired_session_name,
    )
    current_workspace_name = str(current.workspace_window_name or desired_workspace_name).strip() or desired_workspace_name
    current_workspace = find_window(
        context.backend,
        session_name=context.desired_session_name,
        window_name=current_workspace_name,
    )
    if current_workspace is not None:
        kill_window(
            context.backend,
            target=session_window_target(
                context.desired_session_name,
                current_workspace.window_id or current_workspace.window_name,
            ),
        )
    rename_window(
        context.backend,
        target=session_window_target(
            context.desired_session_name,
            temporary_workspace.window_id or temporary_workspace.window_name,
        ),
        new_name=desired_workspace_name,
    )
    control_window = find_window(
        context.backend,
        session_name=context.desired_session_name,
        window_name=context.desired_control_window_name,
    )
    workspace_window = find_window(
        context.backend,
        session_name=context.desired_session_name,
        window_name=desired_workspace_name,
    )
    if workspace_window is not None:
        select_window(
            context.backend,
            target=session_window_target(
                context.desired_session_name,
                workspace_window.window_id or desired_workspace_name,
            ),
        )
    state = build_active_state(
        project_id=controller._project_id,
        current=current,
        namespace_epoch=current.namespace_epoch,
        tmux_socket_path=context.desired_socket_path,
        tmux_session_name=context.desired_session_name,
        layout_version=controller._layout_version,
        layout_signature=context.desired_layout_signature or current.layout_signature,
        control_window_name=context.desired_control_window_name,
        control_window_id=control_window.window_id if control_window is not None else current.control_window_id,
        workspace_window_name=desired_workspace_name,
        workspace_window_id=workspace_window.window_id if workspace_window is not None else current.workspace_window_id,
        workspace_epoch=next_workspace_epoch,
        ui_attachable=True,
        last_started_at=current.last_started_at,
    )
    controller._state_store.save(state)
    controller._event_store.append(
        ProjectNamespaceEvent(
            event_kind='workspace_reflowed',
            project_id=controller._project_id,
            occurred_at=controller._clock(),
            namespace_epoch=current.namespace_epoch,
            tmux_socket_path=context.desired_socket_path,
            tmux_session_name=context.desired_session_name,
            details={'reason': str(reason or '').strip() or 'workspace_reflow'},
        )
    )
    namespace = namespace_from_state(state)
    return ProjectNamespace(
        project_id=namespace.project_id,
        namespace_epoch=namespace.namespace_epoch,
        tmux_socket_path=namespace.tmux_socket_path,
        tmux_session_name=namespace.tmux_session_name,
        layout_version=namespace.layout_version,
        layout_signature=namespace.layout_signature,
        control_window_name=namespace.control_window_name,
        control_window_id=namespace.control_window_id,
        workspace_window_name=namespace.workspace_window_name,
        workspace_window_id=namespace.workspace_window_id,
        workspace_epoch=namespace.workspace_epoch,
        ui_attachable=namespace.ui_attachable,
        created_this_call=False,
        workspace_recreated_this_call=True,
    )


__all__ = ['reflow_project_workspace']
