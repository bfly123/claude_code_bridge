from __future__ import annotations

from typing import Callable

from provider_core.tmux_ownership import (
    apply_session_tmux_identity,
    inspect_tmux_pane_ownership,
    ownership_error_text,
)

from .lifecycle_common import attach_pane_log, live_owned_pane
from .lifecycle_recovery import tmux_rebound_pane


def ensure_pane(
    session,
    *,
    now_str_fn: Callable[[], str],
    attach_pane_log_fn: Callable[[object, object, str], None] = attach_pane_log,
) -> tuple[bool, str]:
    backend = session.backend()
    if not backend:
        return False, 'Terminal backend not available'

    pane_id = session.pane_id
    live_pane = live_owned_pane(session, backend, pane_id)
    if live_pane is not None:
        apply_session_tmux_identity(session, backend, live_pane)
        attach_pane_log_fn(session, backend, live_pane)
        return True, live_pane

    if pane_id and backend.is_alive(pane_id):
        ownership = inspect_tmux_pane_ownership(session, backend, str(pane_id))
        return False, ownership_error_text(ownership, pane_id=str(pane_id))

    if session.terminal == 'tmux':
        rebound = tmux_rebound_pane(
            session,
            backend,
            pane_id,
            now_str_fn=now_str_fn,
            attach_pane_log_fn=attach_pane_log_fn,
        )
        if rebound is not None:
            return rebound

    return False, f'Pane not alive: {pane_id}'


__all__ = ['attach_pane_log', 'ensure_pane']
