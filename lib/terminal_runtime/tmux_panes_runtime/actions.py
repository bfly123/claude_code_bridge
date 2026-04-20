from __future__ import annotations

import subprocess


def split_pane(service, parent_pane_id: str, *, direction: str, percent: int) -> str:
    if not parent_pane_id:
        raise ValueError("parent_pane_id is required")
    _unzoom_parent_if_needed(service, parent_pane_id)
    if service.looks_like_pane_id_fn(parent_pane_id) and not service.pane_exists(parent_pane_id):
        raise RuntimeError(f"Cannot split: pane {parent_pane_id} does not exist")

    pane_size = _read_pane_size(service, parent_pane_id)
    flag, direction_norm = service.normalize_split_direction_fn(direction)
    split_percent = max(1, min(99, int(percent or 50)))
    split_length = _split_length_for_percent(pane_size, direction_norm=direction_norm, percent=split_percent)
    try:
        cp = service.tmux_run_fn(
            split_window_command(parent_pane_id, flag=flag, split_length=split_length),
            check=True,
            capture=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            split_window_error_text(
                exc,
                parent_pane_id=parent_pane_id,
                pane_size=pane_size,
                direction_norm=direction_norm,
            )
        ) from exc

    pane_id = (getattr(cp, "stdout", "") or "").strip()
    if not service.looks_like_pane_id_fn(pane_id):
        raise RuntimeError(f"tmux split-window did not return pane_id: {pane_id!r}")
    return pane_id


def set_pane_title(service, pane_id: str, title: str) -> None:
    if pane_id:
        service.tmux_run_fn(["select-pane", "-t", pane_id, "-T", title or ""], check=False)


def set_pane_user_option(service, pane_id: str, name: str, value: str) -> None:
    if not pane_id:
        return
    opt = service.normalize_user_option_fn(name)
    if not opt:
        return
    service.tmux_run_fn(["set-option", "-p", "-t", pane_id, opt, value or ""], check=False)


def set_pane_style(
    service,
    pane_id: str,
    *,
    border_style: str | None = None,
    active_border_style: str | None = None,
) -> None:
    if not pane_id:
        return
    set_pane_option(service, pane_id, "pane-border-style", border_style)
    set_pane_option(service, pane_id, "pane-active-border-style", active_border_style)


def _unzoom_parent_if_needed(service, parent_pane_id: str) -> None:
    if not service.looks_like_pane_id_fn(parent_pane_id):
        return
    if pane_zoomed(service, parent_pane_id):
        service.tmux_run_fn(["resize-pane", "-Z", "-t", parent_pane_id], check=False, timeout=0.5)


def _read_pane_size(service, parent_pane_id: str) -> str:
    size_cp = service.tmux_run_fn(
        ["display-message", "-p", "-t", parent_pane_id, "#{pane_width}x#{pane_height}"],
        capture=True,
    )
    if getattr(size_cp, "returncode", 1) == 0:
        return (getattr(size_cp, "stdout", "") or "").strip()
    return "unknown"


def split_window_command(parent_pane_id: str, *, flag: str, split_length: int) -> list[str]:
    return [
        "split-window",
        flag,
        "-l",
        str(split_length),
        "-t",
        parent_pane_id,
        "-P",
        "-F",
        "#{pane_id}",
    ]


def split_window_error_text(
    exc: subprocess.CalledProcessError,
    *,
    parent_pane_id: str,
    pane_size: str,
    direction_norm: str,
) -> str:
    out = (getattr(exc, "stdout", "") or "").strip()
    err = (getattr(exc, "stderr", "") or "").strip()
    msg = err or out or "no stdout/stderr"
    command = " ".join(exc.cmd)
    return (
        f"tmux split-window failed (exit {exc.returncode}): {msg}\n"
        f"Pane: {parent_pane_id}, size: {pane_size}, direction: {direction_norm}\n"
        f"Command: {command}\n"
        "Hint: If the pane is zoomed, press Prefix+z to unzoom; also try enlarging terminal window."
    )


def set_pane_option(service, pane_id: str, option: str, value: str | None) -> None:
    if not value:
        return
    service.tmux_run_fn(["set-option", "-p", "-t", pane_id, option, value], check=False)


def pane_zoomed(service, parent_pane_id: str) -> bool:
    try:
        zoom_cp = service.tmux_run_fn(
            ["display-message", "-p", "-t", parent_pane_id, "#{window_zoomed_flag}"],
            capture=True,
            timeout=0.5,
        )
    except Exception:
        return False
    if getattr(zoom_cp, "returncode", 1) != 0:
        return False
    zoomed = (getattr(zoom_cp, "stdout", "") or "").strip()
    return zoomed in {"1", "on", "yes", "true"}


def _split_length_for_percent(pane_size: str, *, direction_norm: str, percent: int) -> int:
    width, height = _parse_pane_size(pane_size)
    basis = width if direction_norm in {"left", "right", "horizontal"} else height
    if basis <= 0:
        basis = 100
    length = round(basis * (percent / 100.0))
    return max(1, min(max(1, basis - 1), int(length)))


def _parse_pane_size(pane_size: str) -> tuple[int, int]:
    text = (pane_size or "").strip().lower()
    if "x" not in text:
        return 0, 0
    width_text, height_text = text.split("x", 1)
    try:
        return int(width_text), int(height_text)
    except Exception:
        return 0, 0


__all__ = [
    "set_pane_style",
    "set_pane_title",
    "set_pane_user_option",
    "split_pane",
]
