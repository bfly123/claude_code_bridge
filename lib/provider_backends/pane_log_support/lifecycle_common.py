from __future__ import annotations

import time
from typing import Callable

from provider_core.tmux_ownership import (
    apply_session_tmux_identity,
    inspect_tmux_pane_ownership,
)


def attach_pane_log(session, backend: object, pane_id: str) -> None:
    ensure = getattr(backend, 'ensure_pane_log', None)
    if callable(ensure):
        try:
            ensure(str(pane_id))
        except Exception:
            pass


def live_owned_pane(session, backend: object, pane_id: str) -> str | None:
    if not pane_id or not backend.is_alive(pane_id):
        return None
    ownership = inspect_tmux_pane_ownership(session, backend, str(pane_id))
    if not ownership.is_owned:
        return None
    return str(pane_id)


def activate_rebound_pane(
    session,
    backend: object,
    pane_id: str,
    *,
    now_str_fn: Callable[[], str],
    attach_pane_log_fn: Callable[[object, object, str], None],
) -> None:
    bind_session_to_pane(session, pane_id, now_str_fn=now_str_fn)
    apply_session_tmux_identity(session, backend, pane_id)
    attach_pane_log_fn(session, backend, pane_id)


def persist_crash_log(session, backend: object, pane_id: str) -> None:
    saver = getattr(backend, 'save_crash_log', None)
    if not callable(saver):
        return
    try:
        runtime = session.runtime_dir
        runtime.mkdir(parents=True, exist_ok=True)
        crash_log = runtime / f'pane-crash-{int(time.time())}.log'
        saver(pane_id, str(crash_log), lines=1000)
    except Exception:
        pass


def pane_exists(backend: object, pane_id: str) -> bool:
    checker = getattr(backend, 'pane_exists', None)
    if not callable(checker):
        return True
    try:
        return bool(checker(pane_id))
    except Exception:
        return True


def bind_session_to_pane(session, pane_id: str, *, now_str_fn: Callable[[], str]) -> None:
    data = getattr(session, 'data', None)
    if not isinstance(data, dict):
        return
    data['pane_id'] = str(pane_id)
    if str(getattr(session, 'terminal', '') or '').strip().lower() == 'tmux':
        data['tmux_session'] = str(pane_id)
    data['updated_at'] = now_str_fn()
    writer = getattr(session, '_write_back', None)
    if callable(writer):
        writer()


__all__ = [
    'activate_rebound_pane',
    'attach_pane_log',
    'bind_session_to_pane',
    'live_owned_pane',
    'pane_exists',
    'persist_crash_log',
]
