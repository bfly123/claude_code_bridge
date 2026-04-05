from __future__ import annotations

import os
import time
from pathlib import Path

from terminal_runtime.tmux import default_detached_session_name as _default_detached_session_name_impl
from terminal_runtime.tmux_attach import parse_session_name as _parse_tmux_session_name_impl
from terminal_runtime.tmux_attach import should_attach_selected_pane as _should_attach_selected_tmux_pane_impl
from terminal_runtime.tmux_input import copy_mode_is_active as _tmux_copy_mode_is_active_impl


def activate_tmux_pane(backend, pane_id: str) -> None:
    pane_id = backend._require_pane_id(pane_id, action="activate_tmux_pane")
    backend._tmux_run(["select-pane", "-t", pane_id], check=False)
    if _should_attach_selected_tmux_pane_impl(env_tmux=os.environ.get("TMUX", "")):
        try:
            cp = backend._tmux_run(["display-message", "-p", "-t", pane_id, "#{session_name}"], capture=True)
            sess = _parse_tmux_session_name_impl(cp.stdout or "")
            if sess:
                backend._tmux_run(["attach", "-t", sess], check=False)
        except Exception:
            pass


def ensure_not_in_copy_mode(backend, pane_id: str) -> None:
    try:
        cp = backend._tmux_run(["display-message", "-p", "-t", pane_id, "#{pane_in_mode}"], capture=True, timeout=1.0)
        if cp.returncode == 0 and _tmux_copy_mode_is_active_impl(cp.stdout or ""):
            backend._tmux_run(["send-keys", "-t", pane_id, "-X", "cancel"], check=False)
    except Exception:
        pass


def send_key(backend, pane_id: str, key: str) -> bool:
    key = (key or "").strip()
    if not pane_id or not key:
        return False
    try:
        cp = backend._tmux_run(["send-keys", "-t", pane_id, key], capture=True, timeout=2.0)
        return cp.returncode == 0
    except Exception:
        return False


def is_alive(backend, pane_id: str) -> bool:
    if not pane_id:
        return False
    if backend._looks_like_tmux_target(pane_id):
        return backend.is_pane_alive(pane_id)
    cp = backend._tmux_run(["has-session", "-t", pane_id], capture=True)
    return cp.returncode == 0


def kill_pane(backend, pane_id: str) -> None:
    if not pane_id:
        return
    if backend._looks_like_tmux_target(pane_id):
        backend.kill_tmux_pane(pane_id)
    else:
        backend._tmux_run(["kill-session", "-t", pane_id], check=False)


def activate(backend, pane_id: str) -> None:
    if not pane_id:
        return
    if backend._looks_like_tmux_target(pane_id):
        backend.activate_tmux_pane(pane_id)
        return
    backend._tmux_run(["attach", "-t", pane_id], check=False)


def save_crash_log(backend, pane_id: str, crash_log_path: str, *, lines: int = 1000) -> None:
    text = backend.get_pane_content(pane_id, lines=lines) or ""
    path = Path(crash_log_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def create_pane(
    backend,
    *,
    cmd: str,
    cwd: str,
    direction: str = "right",
    percent: int = 50,
    parent_pane: str | None = None,
) -> str:
    cmd = (cmd or "").strip()
    cwd = (cwd or ".").strip() or "."

    base: str | None = (parent_pane or "").strip() or None
    if not base:
        try:
            base = backend.get_current_pane_id()
        except Exception:
            base = None

    if base:
        new_pane = backend.split_pane(base, direction=direction, percent=percent)
        if cmd:
            backend.respawn_pane(new_pane, cmd=cmd, cwd=cwd)
        return new_pane

    session_name = _default_detached_session_name_impl(cwd=cwd, pid=os.getpid(), now_ts=time.time())
    backend._tmux_run(["new-session", "-d", "-s", session_name, "-c", cwd], check=True)
    cp = backend._tmux_run(["list-panes", "-t", session_name, "-F", "#{pane_id}"], capture=True, check=True)
    pane_id = (cp.stdout or "").splitlines()[0].strip() if (cp.stdout or "").strip() else ""
    if not backend._looks_like_pane_id(pane_id):
        raise RuntimeError(f"tmux failed to resolve root pane_id for session {session_name!r}")
    if cmd:
        backend.respawn_pane(pane_id, cmd=cmd, cwd=cwd)
    return pane_id


__all__ = [
    "activate",
    "activate_tmux_pane",
    "create_pane",
    "ensure_not_in_copy_mode",
    "is_alive",
    "kill_pane",
    "save_crash_log",
    "send_key",
]
