from __future__ import annotations

import time
from typing import Callable

from provider_core.tmux_ownership import (
    apply_session_tmux_identity,
    inspect_tmux_pane_ownership,
    ownership_error_text,
)


def attach_pane_log(session, backend: object, pane_id: str) -> None:
    ensure = getattr(backend, "ensure_pane_log", None)
    if callable(ensure):
        try:
            ensure(str(pane_id))
        except Exception:
            pass


def ensure_pane(
    session,
    *,
    now_str_fn: Callable[[], str],
    attach_pane_log_fn: Callable[[object, object, str], None] = attach_pane_log,
) -> tuple[bool, str]:
    backend = session.backend()
    if not backend:
        return False, "Terminal backend not available"

    pane_id = session.pane_id

    live_pane = live_owned_pane(session, backend, pane_id)
    if live_pane is not None:
        apply_session_tmux_identity(session, backend, live_pane)
        attach_pane_log_fn(session, backend, live_pane)
        return True, live_pane
    if pane_id and backend.is_alive(pane_id):
        ownership = inspect_tmux_pane_ownership(session, backend, str(pane_id))
        return False, ownership_error_text(ownership, pane_id=str(pane_id))

    if session.terminal == "tmux":
        rebound = tmux_rebound_pane(
            session,
            backend,
            pane_id,
            now_str_fn=now_str_fn,
            attach_pane_log_fn=attach_pane_log_fn,
        )
        if rebound is not None:
            return rebound

    return False, f"Pane not alive: {pane_id}"


def live_owned_pane(session, backend: object, pane_id: str) -> str | None:
    if not pane_id or not backend.is_alive(pane_id):
        return None
    ownership = inspect_tmux_pane_ownership(session, backend, str(pane_id))
    if not ownership.is_owned:
        return None
    return str(pane_id)


def tmux_rebound_pane(
    session,
    backend: object,
    pane_id: str,
    *,
    now_str_fn: Callable[[], str],
    attach_pane_log_fn: Callable[[object, object, str], None],
) -> tuple[bool, str] | None:
    start_cmd = session.start_cmd
    respawn = getattr(backend, "respawn_pane", None)
    create_pane = getattr(backend, "create_pane", None)
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
    return False, f"Pane not alive and respawn failed: {last_err}"


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
    if not callable(respawn) or not pane_id or not str(pane_id).startswith("%"):
        return "respawn unavailable"
    if not _pane_exists(backend, str(pane_id)):
        return "pane target no longer exists"
    ownership = inspect_tmux_pane_ownership(session, backend, str(pane_id))
    if not ownership.is_owned:
        return ownership_error_text(ownership, pane_id=str(pane_id))
    try:
        persist_crash_log(session, backend, str(pane_id))
        respawn(str(pane_id), cmd=start_cmd, cwd=session.work_dir, remain_on_exit=True)
        if not backend.is_alive(str(pane_id)):
            return "respawn did not revive pane"
        activate_rebound_pane(
            session,
            backend,
            str(pane_id),
            now_str_fn=now_str_fn,
            attach_pane_log_fn=attach_pane_log_fn,
        )
        return None
    except Exception as exc:
        return f"{exc}"


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
    try:
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


def activate_rebound_pane(
    session,
    backend: object,
    pane_id: str,
    *,
    now_str_fn: Callable[[], str],
    attach_pane_log_fn: Callable[[object, object, str], None],
) -> None:
    _bind_session_to_pane(session, pane_id, now_str_fn=now_str_fn)
    apply_session_tmux_identity(session, backend, pane_id)
    attach_pane_log_fn(session, backend, pane_id)


def persist_crash_log(session, backend: object, pane_id: str) -> None:
    saver = getattr(backend, "save_crash_log", None)
    if not callable(saver):
        return
    try:
        runtime = session.runtime_dir
        runtime.mkdir(parents=True, exist_ok=True)
        crash_log = runtime / f"pane-crash-{int(time.time())}.log"
        saver(pane_id, str(crash_log), lines=1000)
    except Exception:
        pass


def _pane_exists(backend: object, pane_id: str) -> bool:
    checker = getattr(backend, "pane_exists", None)
    if not callable(checker):
        return True
    try:
        return bool(checker(pane_id))
    except Exception:
        return True


def _bind_session_to_pane(session, pane_id: str, *, now_str_fn: Callable[[], str]) -> None:
    data = getattr(session, "data", None)
    if not isinstance(data, dict):
        return
    data["pane_id"] = str(pane_id)
    if str(getattr(session, "terminal", "") or "").strip().lower() == "tmux":
        data["tmux_session"] = str(pane_id)
    data["updated_at"] = now_str_fn()
    writer = getattr(session, "_write_back", None)
    if callable(writer):
        writer()


__all__ = ["attach_pane_log", "ensure_pane"]
