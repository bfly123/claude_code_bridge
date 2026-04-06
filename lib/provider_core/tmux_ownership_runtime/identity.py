from __future__ import annotations

from .session import session_display_title, session_user_option_lookup


def apply_session_tmux_identity(session, backend, pane_id: str) -> None:
    pane_text = str(pane_id or '').strip()
    if not pane_text:
        return
    pane_title = session_display_title(session)
    title_setter = getattr(backend, 'set_pane_title', None)
    if pane_title and callable(title_setter):
        try:
            title_setter(pane_text, pane_title)
        except Exception:
            pass

    option_setter = getattr(backend, 'set_pane_user_option', None)
    if not callable(option_setter):
        return
    for name, value in session_user_option_lookup(session).items():
        try:
            option_setter(pane_text, name, value)
        except Exception:
            pass


__all__ = ['apply_session_tmux_identity']
