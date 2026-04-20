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


def inside_tmux(
    *,
    env: Mapping[str, str],
    which_fn: Callable[[str], str | None],
    run_fn: Callable,
    current_tty_fn: Callable[[], str | None],
) -> bool:
    if not tmux_env_present(env):
        return False
    if not which_fn("tmux"):
        return False

    tty = current_tty_fn()
    pane = (env.get("TMUX_PANE") or "").strip()

    if pane_tty_matches(run_fn, pane=pane, tty=tty):
        return True
    if client_tty_matches(run_fn, tty=tty):
        return True
    if pane and pane_id_matches(run_fn, pane=pane, tty=tty):
        return True

    return False


def tmux_env_present(env: Mapping[str, str]) -> bool:
    return bool(env.get("TMUX") or env.get("TMUX_PANE"))


def pane_tty_matches(run_fn: Callable, *, pane: str, tty: str | None) -> bool:
    if not pane or not tty:
        return False
    return tmux_value(run_fn, target=pane, format_string="#{pane_tty}") == tty


def client_tty_matches(run_fn: Callable, *, tty: str | None) -> bool:
    if not tty:
        return False
    return tmux_value(run_fn, target=None, format_string="#{client_tty}") == tty


def pane_id_matches(run_fn: Callable, *, pane: str, tty: str | None) -> bool:
    if tty or not pane:
        return False
    pane_id = tmux_value(run_fn, target=pane, format_string="#{pane_id}")
    return pane_id.startswith("%")


def tmux_value(run_fn: Callable, *, target: str | None, format_string: str) -> str:
    command = ["tmux", "display-message", "-p"]
    if target:
        command.extend(["-t", target])
    command.append(format_string)
    try:
        cp = run_fn(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=0.5,
        )
    except Exception:
        return ""
    if cp.returncode != 0:
        return ""
    return (cp.stdout or "").strip()


def detect_terminal(
    *,
    env: Mapping[str, str],
    which_fn: Callable[[str], str | None],
    run_fn: Callable,
    current_tty_fn: Callable[[], str | None],
) -> str | None:
    if inside_tmux(env=env, which_fn=which_fn, run_fn=run_fn, current_tty_fn=current_tty_fn):
        return "tmux"
    return None
