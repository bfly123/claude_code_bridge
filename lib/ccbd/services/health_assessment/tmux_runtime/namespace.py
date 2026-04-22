from __future__ import annotations

from ccbd.services.project_namespace_pane import backend_socket_matches, inspect_project_namespace_pane, same_tmux_socket_path


def pane_outside_project_namespace(*, runtime, namespace_state_store, backend, pane_id: str) -> bool:
    pane_text = _normalized_tmux_pane_id(pane_id)
    if pane_text is None or backend is None or namespace_state_store is None:
        return False
    namespace_state = _load_namespace_state(namespace_state_store)
    if namespace_state is None:
        return False
    backend_ref = _namespace_backend_ref(namespace_state)
    if not _backend_matches_namespace_socket(backend, backend_ref):
        return _runtime_socket_matches_namespace(runtime, backend_ref)
    record = inspect_project_namespace_pane(backend, pane_text)
    return _record_outside_namespace(runtime, namespace_state, record)


def _normalized_tmux_pane_id(pane_id: str) -> str | None:
    pane_text = str(pane_id or '').strip()
    return pane_text if pane_text.startswith('%') else None


def _load_namespace_state(namespace_state_store):
    try:
        return namespace_state_store.load()
    except Exception:
        return None


def _backend_matches_namespace_socket(backend, tmux_socket_path: str | None) -> bool:
    return backend_socket_matches(backend, tmux_socket_path)


def _runtime_socket_matches_namespace(runtime, tmux_socket_path: str | None) -> bool:
    runtime_socket = str(getattr(runtime, 'tmux_socket_path', None) or '').strip()
    return bool(runtime_socket) and same_tmux_socket_path(runtime_socket, tmux_socket_path)


def _record_outside_namespace(runtime, namespace_state, record) -> bool:
    if record is None:
        return True
    slot_key = str(getattr(runtime, 'slot_key', None) or getattr(runtime, 'agent_name', None) or '').strip() or None
    if not record.matches(
        tmux_session_name=_namespace_session_name(namespace_state),
        project_id=runtime.project_id,
        role='agent',
        slot_key=slot_key,
        managed_by='ccbd',
    ):
        return True
    workspace_window_id = str(getattr(namespace_state, 'workspace_window_id', None) or '').strip()
    if workspace_window_id and str(getattr(record, 'window_id', None) or '').strip():
        return str(record.window_id).strip() != workspace_window_id
    return False


def _namespace_backend_ref(namespace_state) -> str | None:
    value = getattr(namespace_state, 'backend_ref', None) or getattr(namespace_state, 'tmux_socket_path', None)
    text = str(value or '').strip()
    return text or None


def _namespace_session_name(namespace_state) -> str:
    value = getattr(namespace_state, 'session_name', None) or getattr(namespace_state, 'tmux_session_name', None)
    return str(value or '').strip()


__all__ = ['pane_outside_project_namespace']
