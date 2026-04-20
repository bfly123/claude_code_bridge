from __future__ import annotations

from collections.abc import Callable


def _missing_pane_state(*, pane_id: str | None, pane_title_marker: str | None) -> str | None:
    if pane_id:
        return None
    return 'missing' if pane_title_marker else None


def _tmux_pane_exists(backend, pane_id: str) -> str | None:
    pane_exists = getattr(backend, 'pane_exists', None)
    if not callable(pane_exists):
        return None
    try:
        return None if pane_exists(pane_id) else 'missing'
    except Exception:
        return 'unknown'


def _tmux_pane_state(
    session,
    backend,
    pane_id: str,
    *,
    inspect_tmux_pane_ownership_fn: Callable,
    backend_pane_alive_fn: Callable[[object, str], bool],
) -> str:
    exists_state = _tmux_pane_exists(backend, pane_id)
    if exists_state is not None:
        return exists_state
    ownership = inspect_tmux_pane_ownership_fn(session, backend, pane_id)
    if not ownership.is_owned:
        return 'foreign'
    return 'alive' if backend_pane_alive_fn(backend, pane_id) else 'dead'


def _generic_pane_state(backend, pane_id: str, *, backend_pane_alive_fn: Callable[[object, str], bool]) -> str:
    return 'alive' if backend_pane_alive_fn(backend, pane_id) else 'dead'


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
    missing_state = _missing_pane_state(pane_id=pane_id, pane_title_marker=pane_title_marker)
    if missing_state is not None:
        return missing_state
    assert pane_id is not None
    if terminal == 'tmux':
        return _tmux_pane_state(
            session,
            backend,
            pane_id,
            inspect_tmux_pane_ownership_fn=inspect_tmux_pane_ownership_fn,
            backend_pane_alive_fn=backend_pane_alive_fn,
        )
    return _generic_pane_state(
        backend,
        pane_id,
        backend_pane_alive_fn=backend_pane_alive_fn,
    )


__all__ = ['resolve_pane_state']
