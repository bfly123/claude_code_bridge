from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TmuxLayoutBackend(Protocol):
    def get_current_pane_id(self) -> str: ...
    def is_alive(self, pane_id: str) -> bool: ...
    def create_pane(self, cmd: str, cwd: str, direction: str = "right", percent: int = 50, parent_pane: str | None = None) -> str: ...
    def split_pane(self, parent_pane_id: str, direction: str, percent: int) -> str: ...
    def set_pane_title(self, pane_id: str, title: str) -> None: ...
    def _tmux_run(self, args: list[str], *, check: bool = False, capture: bool = False, input_bytes: bytes | None = None, timeout: float | None = None): ...


@dataclass(frozen=True)
class LayoutResult:
    panes: dict[str, str]
    root_pane_id: str
    needs_attach: bool
    created_panes: list[str]


def create_tmux_auto_layout(
    providers: list[str],
    *,
    cwd: str,
    backend: TmuxLayoutBackend,
    root_pane_id: str | None = None,
    tmux_session_name: str | None = None,
    percent: int = 50,
    set_markers: bool = True,
    marker_prefix: str = "CCB",
    detached_session_name: str | None = None,
    inside_tmux: bool = False,
) -> LayoutResult:
    if not providers:
        raise ValueError("providers must not be empty")
    if len(providers) > 4:
        raise ValueError("providers max is 4 for auto layout")

    created: list[str] = []
    panes: dict[str, str] = {}
    needs_attach = False

    if root_pane_id:
        root = root_pane_id
    else:
        try:
            root = backend.get_current_pane_id()
        except Exception:
            session_name = (tmux_session_name or detached_session_name or "").strip()
            if session_name:
                if not backend.is_alive(session_name):
                    backend._tmux_run(["new-session", "-d", "-s", session_name, "-c", cwd], check=True)
                cp = backend._tmux_run(["list-panes", "-t", session_name, "-F", "#{pane_id}"], capture=True, check=True)
                root = (cp.stdout or "").splitlines()[0].strip() if (cp.stdout or "").strip() else ""
            else:
                root = backend.create_pane("", cwd)
            if not root or not root.startswith("%"):
                raise RuntimeError("failed to allocate tmux root pane")
            created.append(root)
            needs_attach = not inside_tmux

    panes[providers[0]] = root

    def mark(provider: str, pane_id: str) -> None:
        if not set_markers:
            return
        backend.set_pane_title(pane_id, f"{marker_prefix}-{provider}")

    mark(providers[0], root)

    if len(providers) == 1:
        return LayoutResult(panes=panes, root_pane_id=root, needs_attach=needs_attach, created_panes=created)

    pct = max(1, min(99, int(percent)))

    if len(providers) == 2:
        right = backend.split_pane(root, "right", pct)
        created.append(right)
        panes[providers[1]] = right
        mark(providers[1], right)
        return LayoutResult(panes=panes, root_pane_id=root, needs_attach=needs_attach, created_panes=created)

    if len(providers) == 3:
        right_top = backend.split_pane(root, "right", pct)
        created.append(right_top)
        right_bottom = backend.split_pane(right_top, "bottom", pct)
        created.append(right_bottom)
        panes[providers[1]] = right_top
        panes[providers[2]] = right_bottom
        mark(providers[1], right_top)
        mark(providers[2], right_bottom)
        return LayoutResult(panes=panes, root_pane_id=root, needs_attach=needs_attach, created_panes=created)

    right_top = backend.split_pane(root, "right", pct)
    created.append(right_top)
    left_bottom = backend.split_pane(root, "bottom", pct)
    created.append(left_bottom)
    right_bottom = backend.split_pane(right_top, "bottom", pct)
    created.append(right_bottom)

    panes[providers[1]] = right_top
    panes[providers[2]] = left_bottom
    panes[providers[3]] = right_bottom
    mark(providers[1], right_top)
    mark(providers[2], left_bottom)
    mark(providers[3], right_bottom)
    return LayoutResult(panes=panes, root_pane_id=root, needs_attach=needs_attach, created_panes=created)
