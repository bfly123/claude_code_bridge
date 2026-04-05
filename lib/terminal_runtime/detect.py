from __future__ import annotations

import os
from typing import Callable, Mapping


def current_tty() -> str | None:
    for fd in (0, 1, 2):
        try:
            return os.ttyname(fd)
        except Exception:
            continue
    return None


def inside_tmux(*, env: Mapping[str, str], which_fn: Callable[[str], str | None], run_fn: Callable, current_tty_fn: Callable[[], str | None]) -> bool:
    if not (env.get("TMUX") or env.get("TMUX_PANE")):
        return False
    if not which_fn("tmux"):
        return False

    tty = current_tty_fn()
    pane = (env.get("TMUX_PANE") or "").strip()

    if pane:
        try:
            cp = run_fn(
                ["tmux", "display-message", "-p", "-t", pane, "#{pane_tty}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=0.5,
            )
            pane_tty = (cp.stdout or "").strip()
            if cp.returncode == 0 and tty and pane_tty == tty:
                return True
        except Exception:
            pass

    if tty:
        try:
            cp = run_fn(
                ["tmux", "display-message", "-p", "#{client_tty}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=0.5,
            )
            client_tty = (cp.stdout or "").strip()
            if cp.returncode == 0 and client_tty == tty:
                return True
        except Exception:
            pass

    if not tty and pane:
        try:
            cp = run_fn(
                ["tmux", "display-message", "-p", "-t", pane, "#{pane_id}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=0.5,
            )
            pane_id = (cp.stdout or "").strip()
            if cp.returncode == 0 and pane_id.startswith("%"):
                return True
        except Exception:
            pass

    return False
def detect_terminal(*, env: Mapping[str, str], which_fn: Callable[[str], str | None], run_fn: Callable, current_tty_fn: Callable[[], str | None]) -> str | None:
    if inside_tmux(env=env, which_fn=which_fn, run_fn=run_fn, current_tty_fn=current_tty_fn):
        return "tmux"
    return None
