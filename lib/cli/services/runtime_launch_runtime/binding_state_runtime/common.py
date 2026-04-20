from __future__ import annotations


def build_tmux_backend(binding, *, tmux_backend_cls):
    try:
        return tmux_backend_cls(socket_name=binding.tmux_socket_name, socket_path=binding.tmux_socket_path)
    except TypeError:
        return tmux_backend_cls()


def tmux_target_pane_id(binding, *, runtime_ref: str) -> str:
    return str(binding.active_pane_id or binding.pane_id or runtime_ref[len('tmux:') :]).strip()


__all__ = ['build_tmux_backend', 'tmux_target_pane_id']
