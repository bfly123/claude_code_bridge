from __future__ import annotations

from collections.abc import Callable


def resolve_pane_state(
    session,
    backend,
    *,
    terminal: str,
    pane_id: str | None,
    pane_title_marker: str | None,
    inspect_tmux_pane_ownership_fn: Callable,
    backend_pane_alive_fn: Callable[[object, str], bool],
) -> str | None:
    if not pane_id:
        return 'missing' if pane_title_marker else None
    if terminal == 'tmux' and pane_id:
        pane_exists = getattr(backend, 'pane_exists', None)
        if callable(pane_exists):
            try:
                if not pane_exists(pane_id):
                    return 'missing'
            except Exception:
                return 'unknown'
        ownership = inspect_tmux_pane_ownership_fn(session, backend, pane_id)
        if not ownership.is_owned:
            return 'foreign'
        if backend_pane_alive_fn(backend, pane_id):
            return 'alive'
        return 'dead'
    if backend_pane_alive_fn(backend, pane_id):
        return 'alive'
    if pane_id:
        return 'dead'
    return 'missing'


__all__ = ['resolve_pane_state']
