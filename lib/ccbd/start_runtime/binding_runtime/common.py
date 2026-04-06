from __future__ import annotations


def binding_pane_id(binding) -> str | None:
    pane_id = str(getattr(binding, 'active_pane_id', None) or getattr(binding, 'pane_id', None) or '').strip()
    if not pane_id.startswith('%'):
        return None
    return pane_id


def tmux_backend_for_factory(tmux_backend_factory, *, socket_path: str):
    try:
        return tmux_backend_factory(socket_path=socket_path)
    except TypeError:
        return tmux_backend_factory()


def matching_project_namespace_record(
    *,
    binding,
    tmux_socket_path: str,
    tmux_session_name: str | None,
    agent_name: str,
    project_id: str,
    tmux_backend_factory,
    inspect_project_namespace_pane_fn,
):
    pane_id = binding_pane_id(binding)
    if pane_id is None:
        return None
    session_name = str(tmux_session_name or '').strip()
    if not session_name:
        return None
    backend = tmux_backend_for_factory(tmux_backend_factory, socket_path=tmux_socket_path)
    record = inspect_project_namespace_pane_fn(backend, pane_id)
    if record is None:
        return None
    if not record.matches(
        tmux_session_name=session_name,
        project_id=project_id,
        role='agent',
        slot_key=agent_name,
        managed_by='ccbd',
    ):
        return None
    return record


__all__ = [
    'binding_pane_id',
    'matching_project_namespace_record',
    'tmux_backend_for_factory',
]
