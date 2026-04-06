from __future__ import annotations

from ccbd.services.project_namespace_pane import backend_socket_matches, inspect_project_namespace_pane, same_tmux_socket_path


def pane_outside_project_namespace(*, runtime, namespace_state_store, backend, pane_id: str) -> bool:
    pane_text = str(pane_id or '').strip()
    if backend is None or not pane_text.startswith('%'):
        return False
    if namespace_state_store is None:
        return False
    try:
        namespace_state = namespace_state_store.load()
    except Exception:
        namespace_state = None
    if namespace_state is None:
        return False
    if not backend_socket_matches(backend, namespace_state.tmux_socket_path):
        runtime_socket = str(getattr(runtime, 'tmux_socket_path', None) or '').strip()
        return bool(runtime_socket) and same_tmux_socket_path(runtime_socket, namespace_state.tmux_socket_path)
    record = inspect_project_namespace_pane(backend, pane_text)
    if record is None:
        return True
    return not record.matches(
        tmux_session_name=namespace_state.tmux_session_name,
        project_id=runtime.project_id,
        role='agent',
        slot_key=runtime.agent_name,
        managed_by='ccbd',
    )


__all__ = ['pane_outside_project_namespace']
