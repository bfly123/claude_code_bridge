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
        session_name = selected_session_name(backend, pane_id)
        if session_name:
            backend._tmux_run(["attach", "-t", session_name], check=False)


def ensure_not_in_copy_mode(backend, pane_id: str) -> None:
    pane_mode = capture_tmux_value(backend, pane_id, "#{pane_in_mode}", timeout=1.0)
    if pane_mode and _tmux_copy_mode_is_active_impl(pane_mode):
        backend._tmux_run(["send-keys", "-t", pane_id, "-X", "cancel"], check=False)


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
    base = resolve_parent_pane(backend, parent_pane)

    if base:
        new_pane = backend.split_pane(base, direction=direction, percent=percent)
        respawn_if_requested(backend, new_pane, cmd=cmd, cwd=cwd)
        return new_pane

    pane_id = create_detached_root_pane(backend, cwd=cwd)
    if not backend._looks_like_pane_id(pane_id):
        raise RuntimeError("tmux failed to resolve root pane_id for detached session")
    respawn_if_requested(backend, pane_id, cmd=cmd, cwd=cwd)
    return pane_id


def selected_session_name(backend, pane_id: str) -> str | None:
    session_raw = capture_tmux_value(backend, pane_id, "#{session_name}")
    return _parse_tmux_session_name_impl(session_raw)


def capture_tmux_value(
    backend,
    pane_id: str,
    format_string: str,
    *,
    timeout: float | None = None,
) -> str:
    try:
        cp = backend._tmux_run(
            ["display-message", "-p", "-t", pane_id, format_string],
            capture=True,
            timeout=timeout,
        )
    except Exception:
        return ""
    if cp.returncode != 0:
        return ""
    return (cp.stdout or "").strip()


def resolve_parent_pane(backend, parent_pane: str | None) -> str | None:
    base = (parent_pane or "").strip() or None
    if base:
        return base
    try:
        return backend.get_current_pane_id()
    except Exception:
        return None


def create_detached_root_pane(backend, *, cwd: str) -> str:
    session_name = _default_detached_session_name_impl(cwd=cwd, pid=os.getpid(), now_ts=time.time())
    backend._tmux_run(["new-session", "-d", "-s", session_name, "-c", cwd], check=True)
    cp = backend._tmux_run(
        ["list-panes", "-t", session_name, "-F", "#{pane_id}"],
        capture=True,
        check=True,
    )
    lines = [line.strip() for line in (cp.stdout or "").splitlines() if line.strip()]
    return lines[0] if lines else ""


def respawn_if_requested(backend, pane_id: str, *, cmd: str, cwd: str) -> None:
    if cmd:
        backend.respawn_pane(pane_id, cmd=cmd, cwd=cwd)


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
