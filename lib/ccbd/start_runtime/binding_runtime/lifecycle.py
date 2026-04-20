from __future__ import annotations

from .common import binding_pane_id, tmux_backend_for_factory


def launch_binding_hint(
    *,
    binding,
    raw_binding,
    stale_binding: bool,
    assigned_pane_id: str | None,
    tmux_socket_path: str | None,
    same_tmux_socket_path_fn,
):
    if binding is not None:
        return binding
    if not stale_binding:
        return None
    if assigned_pane_id and same_tmux_socket_path_fn(getattr(raw_binding, 'tmux_socket_path', None), tmux_socket_path):
        return None
    return raw_binding


def relabel_project_namespace_pane(
    *,
    binding,
    agent_name: str,
    project_id: str,
    style_index: int,
    tmux_socket_path: str | None,
    namespace_epoch: int | None,
    tmux_backend_factory,
    same_tmux_socket_path_fn,
    apply_ccb_pane_identity_fn,
) -> str | None:
    if not same_tmux_socket_path_fn(getattr(binding, 'tmux_socket_path', None), tmux_socket_path):
        return None
    pane_id = binding_pane_id(binding)
    if pane_id is None:
        return None
    socket_path = str(tmux_socket_path or '').strip()
    if not socket_path:
        return None
    backend = tmux_backend_for_factory(tmux_backend_factory, socket_path=socket_path)
    if not callable(getattr(backend, 'set_pane_title', None)):
        return None
    if not callable(getattr(backend, 'set_pane_user_option', None)):
        return None
    apply_ccb_pane_identity_fn(
        backend,
        pane_id,
        title=agent_name,
        agent_label=agent_name,
        project_id=project_id,
        order_index=style_index,
        slot_key=agent_name,
        namespace_epoch=namespace_epoch,
        managed_by='ccbd',
    )
    return pane_id


__all__ = [
    'launch_binding_hint',
    'relabel_project_namespace_pane',
]
