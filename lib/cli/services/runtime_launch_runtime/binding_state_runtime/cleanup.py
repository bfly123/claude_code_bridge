from __future__ import annotations

from .common import build_tmux_backend


def cleanup_stale_tmux_binding(binding, *, tmux_backend_cls, kill_tmux_pane_fn) -> None:
    if binding is None:
        return
    runtime_ref = str(binding.runtime_ref or '').strip()
    if not runtime_ref.startswith('tmux:'):
        return
    pane_state = str(binding.pane_state or '').strip().lower()
    if pane_state not in {'dead', 'missing'}:
        return
    pane_id = str(binding.pane_id or binding.active_pane_id or '').strip()
    if not pane_id.startswith('%'):
        return
    try:
        backend = build_tmux_backend(binding, tmux_backend_cls=tmux_backend_cls)
    except Exception:
        return
    kill_tmux_pane_fn(backend, pane_id)


__all__ = ['cleanup_stale_tmux_binding']
