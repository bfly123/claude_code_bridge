from __future__ import annotations

from .models import ProjectNamespace, ProjectNamespaceDestroySummary
from ..project_namespace_state import ProjectNamespaceEvent, ProjectNamespaceState


def normalized_layout_signature(layout_signature: str | None) -> str | None:
    return str(layout_signature or '').strip() or None


def build_active_state(
    *,
    project_id: str,
    current,
    namespace_epoch: int,
    tmux_socket_path: str,
    tmux_session_name: str,
    layout_version: int,
    layout_signature: str | None,
    control_window_name: str | None,
    control_window_id: str | None,
    workspace_window_name: str | None,
    workspace_window_id: str | None,
    workspace_epoch: int,
    ui_attachable: bool,
    last_started_at: str | None,
    backend_family: str | None = None,
    backend_impl: str | None = None,
):
    return ProjectNamespaceState(
        project_id=project_id,
        namespace_epoch=namespace_epoch,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        layout_version=layout_version,
        layout_signature=layout_signature,
        control_window_name=control_window_name,
        control_window_id=control_window_id,
        workspace_window_name=workspace_window_name,
        workspace_window_id=workspace_window_id,
        workspace_epoch=workspace_epoch,
        ui_attachable=ui_attachable,
        last_started_at=last_started_at,
        last_destroyed_at=current.last_destroyed_at if current is not None else None,
        last_destroy_reason=current.last_destroy_reason if current is not None else None,
        backend_family=backend_family or (getattr(current, 'backend_family', None) if current is not None else None),
        backend_impl=backend_impl or (getattr(current, 'backend_impl', None) if current is not None else None),
    )


def build_created_event(
    *,
    project_id: str,
    occurred_at: str,
    namespace_epoch: int,
    tmux_socket_path: str,
    tmux_session_name: str,
    recreated: bool,
    reason: str,
):
    return ProjectNamespaceEvent(
        event_kind='namespace_created',
        project_id=project_id,
        occurred_at=occurred_at,
        namespace_epoch=namespace_epoch,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        details={'recreated': recreated, 'reason': reason},
    )


def build_destroyed_state(
    *,
    current,
    project_id: str,
    occurred_at: str,
    reason: str,
    tmux_socket_path: str,
    tmux_session_name: str,
    layout_version: int,
    control_window_name: str | None,
    workspace_window_name: str | None,
):
    if current is not None:
        return current.with_destroyed(occurred_at=occurred_at, reason=reason)
    return ProjectNamespaceState(
        project_id=project_id,
        namespace_epoch=1,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        layout_version=layout_version,
        control_window_name=control_window_name,
        workspace_window_name=workspace_window_name,
        ui_attachable=False,
        last_started_at=None,
        last_destroyed_at=occurred_at,
        last_destroy_reason=reason,
        backend_family=None,
        backend_impl=None,
    )


def build_destroyed_event(
    *,
    project_id: str,
    occurred_at: str,
    namespace_epoch: int,
    tmux_socket_path: str,
    tmux_session_name: str,
    destroyed: bool,
    reason: str,
):
    return ProjectNamespaceEvent(
        event_kind='namespace_destroyed',
        project_id=project_id,
        occurred_at=occurred_at,
        namespace_epoch=namespace_epoch,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        details={'destroyed': destroyed, 'reason': reason},
    )


def build_destroy_summary(
    *,
    project_id: str,
    namespace_epoch: int | None,
    tmux_socket_path: str,
    tmux_session_name: str,
    destroyed: bool,
    reason: str,
) -> ProjectNamespaceDestroySummary:
    return ProjectNamespaceDestroySummary(
        project_id=project_id,
        namespace_epoch=namespace_epoch,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        destroyed=destroyed,
        reason=reason,
    )


def namespace_from_state(state) -> ProjectNamespace:
    return ProjectNamespace.from_state(state)


__all__ = [
    'build_active_state',
    'build_created_event',
    'build_destroy_summary',
    'build_destroyed_event',
    'build_destroyed_state',
    'namespace_from_state',
    'normalized_layout_signature',
]
