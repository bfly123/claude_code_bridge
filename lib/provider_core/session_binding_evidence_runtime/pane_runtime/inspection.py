from __future__ import annotations

from collections.abc import Callable


def inspect_session_pane(
    session,
    *,
    session_backend_fn: Callable,
    session_pane_title_marker_fn: Callable,
    resolve_pane_state_fn: Callable,
) -> dict[str, str | None]:
    terminal = str(getattr(session, 'terminal', '') or '').strip() or 'tmux'
    pane_id = str(getattr(session, 'pane_id', '') or '').strip() or None
    pane_title_marker = session_pane_title_marker_fn(session)
    backend = session_backend_fn(session)
    if backend is None:
        return {
            'terminal': terminal,
            'pane_id': pane_id,
            'active_pane_id': pane_id,
            'pane_title_marker': pane_title_marker,
            'pane_state': 'unknown' if pane_id else ('missing' if pane_title_marker else None),
        }
    pane_state = resolve_pane_state_fn(
        session,
        backend,
        terminal=terminal,
        pane_id=pane_id,
        pane_title_marker=pane_title_marker,
    )
    active_pane_id = pane_id if pane_state == 'alive' else None
    return {
        'terminal': terminal,
        'pane_id': pane_id,
        'active_pane_id': active_pane_id,
        'pane_title_marker': pane_title_marker,
        'pane_state': pane_state,
    }


__all__ = ['inspect_session_pane']
