from __future__ import annotations


def session_backend(session):
    backend_factory = getattr(session, 'backend', None)
    if not callable(backend_factory):
        return None
    try:
        return backend_factory()
    except Exception:
        return None


def backend_pane_alive(backend, pane_id: str | None) -> bool:
    pane_text = str(pane_id or '').strip()
    if not pane_text:
        return False
    checker = getattr(backend, 'is_tmux_pane_alive', None)
    if not callable(checker):
        checker = getattr(backend, 'is_alive', None)
    if not callable(checker):
        return False
    try:
        return bool(checker(pane_text))
    except Exception:
        return False


__all__ = ['backend_pane_alive', 'session_backend']
