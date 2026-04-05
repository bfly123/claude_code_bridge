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

    if pane_id and backend.is_alive(pane_id):
        ownership = inspect_tmux_pane_ownership(session, backend, str(pane_id))
        if not ownership.is_owned:
            return False, ownership_error_text(ownership, pane_id=str(pane_id))
        apply_session_tmux_identity(session, backend, str(pane_id))
        attach_pane_log_fn(session, backend, pane_id)
        return True, pane_id

    if session.terminal == "tmux":
        start_cmd = session.start_cmd
        respawn = getattr(backend, "respawn_pane", None)
        create_pane = getattr(backend, "create_pane", None)
        if start_cmd and (callable(respawn) or callable(create_pane)):
            last_err: str | None = None
            target = pane_id
            if callable(respawn) and target and str(target).startswith("%"):
                if not _pane_exists(backend, str(target)):
                    last_err = "pane target no longer exists"
                else:
                    ownership = inspect_tmux_pane_ownership(session, backend, str(target))
                    if not ownership.is_owned:
                        last_err = ownership_error_text(ownership, pane_id=str(target))
                    else:
                        try:
                            saver = getattr(backend, "save_crash_log", None)
                            if callable(saver):
                                try:
                                    runtime = session.runtime_dir
                                    runtime.mkdir(parents=True, exist_ok=True)
                                    crash_log = runtime / f"pane-crash-{int(time.time())}.log"
                                    saver(str(target), str(crash_log), lines=1000)
                                except Exception:
                                    pass
                            respawn(str(target), cmd=start_cmd, cwd=session.work_dir, remain_on_exit=True)
                            if backend.is_alive(str(target)):
                                _bind_session_to_pane(session, str(target), now_str_fn=now_str_fn)
                                apply_session_tmux_identity(session, backend, str(target))
                                attach_pane_log_fn(session, backend, str(target))
                                return True, str(target)
                            last_err = "respawn did not revive pane"
                        except Exception as exc:
                            last_err = f"{exc}"
            if callable(create_pane):
                try:
                    new_pane = create_pane(start_cmd, session.work_dir)
                    if new_pane and backend.is_alive(str(new_pane)):
                        _bind_session_to_pane(session, str(new_pane), now_str_fn=now_str_fn)
                        apply_session_tmux_identity(session, backend, str(new_pane))
                        attach_pane_log_fn(session, backend, str(new_pane))
                        return True, str(new_pane)
                    last_err = "create_pane did not produce a live pane"
                except Exception as exc:
                    last_err = f"{exc}"
            if last_err:
                return False, f"Pane not alive and respawn failed: {last_err}"

    return False, f"Pane not alive: {pane_id}"


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
