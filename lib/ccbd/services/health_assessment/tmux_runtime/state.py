from __future__ import annotations

from .ownership import inspect_tmux_pane_ownership


def tmux_pane_state(session, backend, pane_id: str) -> str:
    pane_text = normalized_pane_id(pane_id)
    if backend is None or not pane_text:
        return 'missing'
    existence = pane_existence_state(backend, pane_text)
    if existence is not None:
        return existence
    ownership = inspect_tmux_pane_ownership(session, backend, pane_text)
    if not ownership.is_owned:
        return 'foreign'
    alive_state = pane_alive_state(backend, pane_text)
    if alive_state is not None:
        return alive_state
    return 'missing'


def normalized_pane_id(pane_id: str) -> str:
    return str(pane_id or '').strip()


def pane_existence_state(backend, pane_id: str) -> str | None:
    pane_exists = getattr(backend, 'pane_exists', None)
    if not callable(pane_exists):
        return None
    try:
        return None if pane_exists(pane_id) else 'missing'
    except Exception:
        return 'missing'


def pane_alive_state(backend, pane_id: str) -> str | None:
    tmux_alive = bool_backend_call(backend, 'is_tmux_pane_alive', pane_id)
    if tmux_alive is not None:
        return 'alive' if tmux_alive else 'dead'
    alive = bool_backend_call(backend, 'is_alive', pane_id)
    if alive is not None:
        return 'alive' if alive else 'dead'
    return None


def bool_backend_call(backend, method_name: str, pane_id: str) -> bool | None:
    method = getattr(backend, method_name, None)
    if not callable(method):
        return None
    try:
        return bool(method(pane_id))
    except Exception:
        return None


__all__ = ['tmux_pane_state']
