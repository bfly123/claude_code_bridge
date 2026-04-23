from __future__ import annotations

from .backend import find_window, kill_server, session_window_target, window_root_pane
from .ensure_context import rebuild_namespace_backend
from .ensure_identity import apply_namespace_identity
from .models import ProjectNamespace
from .records import (
    build_active_state,
    build_created_event,
    namespace_from_state,
)
from ..project_namespace_state import next_namespace_epoch


def force_recreate_namespace(controller, context):
    if not context.session_is_alive:
        return context
    kill_server(context.backend, session_name=context.desired_session_name)
    return context.with_updates(
        backend=rebuild_namespace_backend(
            controller,
            socket_path=context.desired_socket_path,
        ),
        session_is_alive=False,
        recreate_cause=context.recreate_cause or 'forced_recreate',
    )


def layout_recreate_reason(controller, *, current, desired_layout_signature: str | None) -> str | None:
    if current is None:
        return None
    if int(current.layout_version) != controller._layout_version:
        return 'layout_version_changed'
    if desired_layout_signature is None:
        return None
    if str(current.layout_signature or '').strip() != desired_layout_signature:
        return 'layout_signature_changed'
    return None


def recreate_for_layout_change(controller, context):
    if not context.session_is_alive:
        return context
    reason = layout_recreate_reason(
        controller,
        current=context.current,
        desired_layout_signature=context.desired_layout_signature,
    )
    if reason is None:
        return context
    kill_server(context.backend, session_name=context.desired_session_name)
    return context.with_updates(
        backend=rebuild_namespace_backend(
            controller,
            socket_path=context.desired_socket_path,
        ),
        session_is_alive=False,
        recreate_cause=reason,
    )


def persist_refreshed_namespace(controller, context) -> ProjectNamespace:
    current = context.current
    if current is None:
        raise ValueError('persist_refreshed_namespace requires current state')
    control_window_name = str(current.control_window_name or context.desired_control_window_name)
    workspace_window_name = str(current.workspace_window_name or context.desired_workspace_window_name)
    control_window = find_window(
        context.backend,
        session_name=context.desired_session_name,
        window_name=control_window_name,
    )
    workspace_window = find_window(
        context.backend,
        session_name=context.desired_session_name,
        window_name=workspace_window_name,
    )
    root_pane = window_root_pane(
        context.backend,
        target_window=session_window_target(context.desired_session_name, workspace_window_name),
    )
    apply_namespace_identity(
        controller,
        backend=context.backend,
        pane_id=root_pane,
        namespace_epoch=current.namespace_epoch,
        tmux_socket_path=context.desired_socket_path,
        tmux_session_name=context.desired_session_name,
    )
    state = build_active_state(
        project_id=controller._project_id,
        current=current,
        namespace_epoch=current.namespace_epoch,
        tmux_socket_path=context.desired_socket_path,
        tmux_session_name=context.desired_session_name,
        layout_version=controller._layout_version,
        layout_signature=context.desired_layout_signature or current.layout_signature,
        control_window_name=control_window_name,
        control_window_id=control_window.window_id if control_window is not None else current.control_window_id,
        workspace_window_name=workspace_window_name,
        workspace_window_id=workspace_window.window_id if workspace_window is not None else current.workspace_window_id,
        workspace_epoch=max(1, int(current.workspace_epoch)),
        ui_attachable=True,
        last_started_at=current.last_started_at,
        backend_family=getattr(context.backend, 'backend_family', None),
        backend_impl=getattr(context.backend, 'backend_impl', None),
    )
    controller._state_store.save(state)
    return namespace_from_state(state)


def build_created_namespace(controller, context) -> ProjectNamespace:
    current = context.current
    occurred_at = controller._clock()
    epoch = next_namespace_epoch(current)
    control_window = find_window(
        context.backend,
        session_name=context.desired_session_name,
        window_name=context.desired_control_window_name,
    )
    workspace_window = find_window(
        context.backend,
        session_name=context.desired_session_name,
        window_name=context.desired_workspace_window_name,
    )
    state = build_active_state(
        project_id=controller._project_id,
        current=current,
        namespace_epoch=epoch,
        tmux_socket_path=context.desired_socket_path,
        tmux_session_name=context.desired_session_name,
        layout_version=controller._layout_version,
        layout_signature=context.desired_layout_signature,
        control_window_name=context.desired_control_window_name,
        control_window_id=control_window.window_id if control_window is not None else None,
        workspace_window_name=context.desired_workspace_window_name,
        workspace_window_id=workspace_window.window_id if workspace_window is not None else None,
        workspace_epoch=1,
        ui_attachable=True,
        last_started_at=occurred_at,
        backend_family=getattr(context.backend, 'backend_family', None),
        backend_impl=getattr(context.backend, 'backend_impl', None),
    )
    controller._state_store.save(state)
    controller._event_store.append(
        build_created_event(
            project_id=controller._project_id,
            occurred_at=occurred_at,
            namespace_epoch=epoch,
            tmux_socket_path=context.desired_socket_path,
            tmux_session_name=context.desired_session_name,
            recreated=bool(current is not None),
            reason=context.recreate_cause
            or ('missing_session' if current is not None else 'initial_create'),
        )
    )
    return ProjectNamespace(
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
        backend_family=getattr(state, 'backend_family', None),
        backend_impl=getattr(state, 'backend_impl', None),
        created_this_call=True,
    )


__all__ = [
    'build_created_namespace',
    'force_recreate_namespace',
    'layout_recreate_reason',
    'persist_refreshed_namespace',
    'recreate_for_layout_change',
]
