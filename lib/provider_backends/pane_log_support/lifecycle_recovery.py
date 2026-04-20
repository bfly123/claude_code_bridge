from __future__ import annotations

from typing import Callable

from provider_core.tmux_ownership import inspect_tmux_pane_ownership, ownership_error_text

from .lifecycle_common import (
    activate_rebound_pane,
    pane_exists,
    persist_crash_log,
)


def tmux_rebound_pane(
    session,
    backend: object,
    pane_id: str,
    *,
    now_str_fn: Callable[[], str],
    attach_pane_log_fn: Callable[[object, object, str], None],
) -> tuple[bool, str] | None:
    start_cmd = session.start_cmd
    respawn = getattr(backend, 'respawn_pane', None)
    create_pane = getattr(backend, 'create_pane', None)
    if not start_cmd or (not callable(respawn) and not callable(create_pane)):
        return None

    last_err = respawn_existing_pane(
        session,
        backend,
        pane_id,
        start_cmd=start_cmd,
        respawn=respawn,
        now_str_fn=now_str_fn,
        attach_pane_log_fn=attach_pane_log_fn,
    )
    if last_err is None:
        return True, str(pane_id)

    created = create_replacement_pane(
        session,
        backend,
        start_cmd=start_cmd,
        create_pane=create_pane,
        now_str_fn=now_str_fn,
        attach_pane_log_fn=attach_pane_log_fn,
    )
    if created is not None:
        return True, created
    return False, f'Pane not alive and respawn failed: {last_err}'


def respawn_existing_pane(
    session,
    backend: object,
    pane_id: str,
    *,
    start_cmd: str,
    respawn,
    now_str_fn: Callable[[], str],
    attach_pane_log_fn: Callable[[object, object, str], None],
) -> str | None:
    if not callable(respawn) or not pane_id or not str(pane_id).startswith('%'):
        return 'respawn unavailable'
    if not pane_exists(backend, str(pane_id)):
        return 'pane target no longer exists'
    ownership = inspect_tmux_pane_ownership(session, backend, str(pane_id))
    if not ownership.is_owned:
        return ownership_error_text(ownership, pane_id=str(pane_id))
    try:
        persist_crash_log(session, backend, str(pane_id))
        respawn(str(pane_id), cmd=start_cmd, cwd=session.work_dir, remain_on_exit=True)
        if not backend.is_alive(str(pane_id)):
            return 'respawn did not revive pane'
        activate_rebound_pane(
            session,
            backend,
            str(pane_id),
            now_str_fn=now_str_fn,
            attach_pane_log_fn=attach_pane_log_fn,
        )
        return None
    except Exception as exc:
        return f'{exc}'


def create_replacement_pane(
    session,
    backend: object,
    *,
    start_cmd: str,
    create_pane,
    now_str_fn: Callable[[], str],
    attach_pane_log_fn: Callable[[object, object, str], None],
) -> str | None:
    if not callable(create_pane):
        return None
    data = getattr(session, 'data', None)
    parent_pane = None
    if isinstance(data, dict):
        parent_pane_text = str(data.get('ccb_replacement_parent_pane') or '').strip()
        if parent_pane_text.startswith('%'):
            parent_pane = parent_pane_text
    try:
        if parent_pane is not None:
            new_pane = create_pane(start_cmd, session.work_dir, parent_pane=parent_pane)
        else:
            new_pane = create_pane(start_cmd, session.work_dir)
    except Exception:
        return None
    if not new_pane or not backend.is_alive(str(new_pane)):
        return None
    activate_rebound_pane(
        session,
        backend,
        str(new_pane),
        now_str_fn=now_str_fn,
        attach_pane_log_fn=attach_pane_log_fn,
    )
    return str(new_pane)


__all__ = [
    'create_replacement_pane',
    'respawn_existing_pane',
    'tmux_rebound_pane',
]
