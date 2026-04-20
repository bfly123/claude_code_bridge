from __future__ import annotations

from provider_core.tmux_ownership import inspect_tmux_pane_ownership

from .backend import backend_pane_alive, session_backend
from .fields import session_pane_title_marker
from .pane_runtime import inspect_session_pane as _inspect_session_pane_impl
from .pane_runtime import resolve_pane_state as _resolve_pane_state_impl


def inspect_session_pane(session) -> dict[str, str | None]:
    return _inspect_session_pane_impl(
        session,
        session_backend_fn=session_backend,
        session_pane_title_marker_fn=session_pane_title_marker,
        resolve_pane_state_fn=resolve_pane_state,
    )


def resolve_pane_state(session, backend, *, terminal: str, pane_id: str | None, pane_title_marker: str | None) -> str | None:
    return _resolve_pane_state_impl(
        session,
        backend,
        terminal=terminal,
        pane_id=pane_id,
        pane_title_marker=pane_title_marker,
        inspect_tmux_pane_ownership_fn=inspect_tmux_pane_ownership,
        backend_pane_alive_fn=backend_pane_alive,
    )


__all__ = ['inspect_session_pane', 'resolve_pane_state']
