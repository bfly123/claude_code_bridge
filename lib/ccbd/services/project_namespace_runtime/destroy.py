from __future__ import annotations

from .backend import build_backend, kill_server
from .records import build_destroy_summary, build_destroyed_event, build_destroyed_state


def destroy_project_namespace(controller, *, reason: str):
    normalized_reason = str(reason or '').strip() or 'destroyed'
    controller._layout.ccbd_dir.mkdir(parents=True, exist_ok=True)
    current = controller._state_store.load()
    occurred_at = controller._clock()
    tmux_socket_path = str(current.tmux_socket_path) if current is not None else str(controller._layout.ccbd_tmux_socket_path)
    tmux_session_name = str(current.tmux_session_name) if current is not None else controller._layout.ccbd_tmux_session_name
    backend = build_backend(controller._backend_factory, socket_path=tmux_socket_path)
    destroyed = kill_server(backend)
    next_state = build_destroyed_state(
        current=current,
        project_id=controller._project_id,
        occurred_at=occurred_at,
        reason=normalized_reason,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        layout_version=controller._layout_version,
    )
    controller._state_store.save(next_state)
    controller._event_store.append(
        build_destroyed_event(
            project_id=controller._project_id,
            occurred_at=occurred_at,
            namespace_epoch=next_state.namespace_epoch,
            tmux_socket_path=tmux_socket_path,
            tmux_session_name=tmux_session_name,
            destroyed=destroyed,
            reason=normalized_reason,
        )
    )
    return build_destroy_summary(
        project_id=controller._project_id,
        namespace_epoch=next_state.namespace_epoch,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        destroyed=destroyed,
        reason=normalized_reason,
    )


__all__ = ['destroy_project_namespace']
