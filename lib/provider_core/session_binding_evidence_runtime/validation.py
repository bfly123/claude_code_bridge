from __future__ import annotations

from provider_core.tmux_ownership import inspect_tmux_pane_ownership

from .backend import session_backend
from .validation_checks import ensured_pane_id, session_attr_text, session_liveness_checker, should_validate_session


def session_binding_is_usable(session, *, sleep_fn) -> bool:
    if not should_validate_session(session):
        return True
    pane_id = ensured_pane_id(session)
    if pane_id is None:
        return True
    if pane_id == '':
        return False
    if not binding_is_stable(session, pane_id, sleep_fn=sleep_fn):
        return False
    return binding_has_owned_tmux_pane(session, pane_id)


def binding_is_stable(session, pane_or_err: object, *, delay_s: float = 0.1, sleep_fn) -> bool:
    backend = session_backend(session)
    if backend is None:
        return True
    pane_id = str(pane_or_err or session_attr_text(session, 'pane_id') or '').strip()
    if not pane_id:
        return False
    checker = session_liveness_checker(backend)
    if checker is None:
        return True
    try:
        if not checker(pane_id):
            return False
        sleep_fn(delay_s)
        return bool(checker(pane_id))
    except Exception:
        return False


def binding_has_owned_tmux_pane(session, pane_id: str | None) -> bool:
    terminal = str(getattr(session, 'terminal', '') or '').strip().lower()
    if terminal != 'tmux':
        return True
    backend = session_backend(session)
    if backend is None:
        return True
    ownership = inspect_tmux_pane_ownership(session, backend, str(pane_id or '').strip())
    return ownership.is_owned


__all__ = ['session_binding_is_usable']
