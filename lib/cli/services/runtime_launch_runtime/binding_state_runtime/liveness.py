from __future__ import annotations

from .common import build_tmux_backend, tmux_target_pane_id


def binding_runtime_alive(binding, *, tmux_backend_cls) -> bool:
    identity_state = str(getattr(binding, 'provider_identity_state', None) or '').strip().lower()
    if identity_state and identity_state != 'match':
        return False
    runtime_ref = str(binding.runtime_ref or '').strip()
    if not runtime_ref:
        return False
    if not runtime_ref.startswith('tmux:'):
        return True
    pane_state = str(binding.pane_state or '').strip().lower()
    if pane_state not in {'', 'alive'}:
        return False
    target = tmux_target_pane_id(binding, runtime_ref=runtime_ref)
    if not target.startswith('%'):
        return False
    try:
        backend = build_tmux_backend(binding, tmux_backend_cls=tmux_backend_cls)
        return backend.is_tmux_pane_alive(target)
    except Exception:
        return False


__all__ = ['binding_runtime_alive']
