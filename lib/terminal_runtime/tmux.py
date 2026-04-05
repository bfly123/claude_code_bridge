from __future__ import annotations

from pathlib import Path


def tmux_base(socket_name: str | None = None, *, socket_path: str | None = None) -> list[str]:
    cmd = ["tmux"]
    if socket_path:
        cmd.extend(["-S", str(Path(socket_path).expanduser())])
    elif socket_name:
        cmd.extend(["-L", socket_name])
    return cmd


def normalize_socket_name(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    return None if text == "default" else text


def socket_name_from_tmux_env(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    socket_path = text.split(",", 1)[0].strip()
    if not socket_path:
        return None
    return normalize_socket_name(Path(socket_path).name)


def looks_like_pane_id(value: str) -> bool:
    return (value or "").strip().startswith("%")


def looks_like_tmux_target(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return False
    return v.startswith("%") or (":" in v) or ("." in v)


def normalize_split_direction(direction: str) -> tuple[str, str]:
    direction_norm = (direction or "").strip().lower()
    if direction_norm in ("right", "h", "horizontal"):
        return "-h", "right"
    if direction_norm in ("bottom", "v", "vertical"):
        return "-v", "bottom"
    raise ValueError(f"unsupported direction: {direction!r} (use 'right' or 'bottom')")


def pane_id_by_title_marker_output(stdout: str, marker: str) -> str | None:
    marker = (marker or "").strip()
    if not marker:
        return None
    exact_matches: list[str] = []
    prefix_matches: list[str] = []
    for line in (stdout or "").splitlines():
        if not line.strip():
            continue
        if "\t" in line:
            pid, title = line.split("\t", 1)
        else:
            parts = line.split(" ", 1)
            pid, title = (parts[0], parts[1] if len(parts) > 1 else "")
        pid = pid.strip()
        if not looks_like_pane_id(pid):
            continue
        normalized_title = (title or "").strip()
        if normalized_title == marker:
            exact_matches.append(pid)
            continue
        if normalized_title.startswith(marker):
            prefix_matches.append(pid)
    if len(exact_matches) == 1:
        return exact_matches[0]
    if exact_matches:
        return None
    if len(prefix_matches) == 1:
        return prefix_matches[0]
    return None


def default_detached_session_name(*, cwd: str, pid: int, now_ts: float) -> str:
    return f"ccb-{Path(cwd).name}-{int(now_ts) % 100000}-{pid}"
