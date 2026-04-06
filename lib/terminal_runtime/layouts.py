from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TmuxLayoutBackend(Protocol):
    def get_current_pane_id(self) -> str: ...
    def is_alive(self, pane_id: str) -> bool: ...
    def create_pane(
        self,
        cmd: str,
        cwd: str,
        direction: str = "right",
        percent: int = 50,
        parent_pane: str | None = None,
    ) -> str: ...
    def split_pane(self, parent_pane_id: str, direction: str, percent: int) -> str: ...
    def set_pane_title(self, pane_id: str, title: str) -> None: ...
    def _tmux_run(
        self,
        args: list[str],
        *,
        check: bool = False,
        capture: bool = False,
        input_bytes: bytes | None = None,
        timeout: float | None = None,
    ): ...


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

    panes: dict[str, str] = {}
    root, needs_attach, created = resolve_root_pane(
        backend,
        cwd=cwd,
        root_pane_id=root_pane_id,
        tmux_session_name=tmux_session_name,
        detached_session_name=detached_session_name,
        inside_tmux=inside_tmux,
    )

    panes[providers[0]] = root
    mark = build_marker(backend, enabled=set_markers, marker_prefix=marker_prefix)
    mark(providers[0], root)

    if len(providers) == 1:
        return build_layout_result(panes, root, needs_attach=needs_attach, created=created)

    pct = max(1, min(99, int(percent)))
    build_split_layout(backend, providers, panes, created, root=root, percent=pct, mark=mark)
    return build_layout_result(panes, root, needs_attach=needs_attach, created=created)


def resolve_root_pane(
    backend: TmuxLayoutBackend,
    *,
    cwd: str,
    root_pane_id: str | None,
    tmux_session_name: str | None,
    detached_session_name: str | None,
    inside_tmux: bool,
) -> tuple[str, bool, list[str]]:
    if root_pane_id:
        return root_pane_id, False, []
    try:
        return backend.get_current_pane_id(), False, []
    except Exception:
        root = detached_root_pane(
            backend,
            cwd=cwd,
            session_name=(tmux_session_name or detached_session_name or "").strip(),
        )
        return root, not inside_tmux, [root]


def detached_root_pane(backend: TmuxLayoutBackend, *, cwd: str, session_name: str) -> str:
    if session_name:
        if not backend.is_alive(session_name):
            backend._tmux_run(["new-session", "-d", "-s", session_name, "-c", cwd], check=True)
        cp = backend._tmux_run(
            ["list-panes", "-t", session_name, "-F", "#{pane_id}"],
            capture=True,
            check=True,
        )
        root = first_pane_id(cp.stdout or "")
    else:
        root = backend.create_pane("", cwd)
    if not root or not root.startswith("%"):
        raise RuntimeError("failed to allocate tmux root pane")
    return root


def first_pane_id(stdout: str) -> str:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    return lines[0] if lines else ""


def build_marker(
    backend: TmuxLayoutBackend,
    *,
    enabled: bool,
    marker_prefix: str,
):
    def mark(provider: str, pane_id: str) -> None:
        if not enabled:
            return
        backend.set_pane_title(pane_id, f"{marker_prefix}-{provider}")

    return mark


def build_split_layout(
    backend: TmuxLayoutBackend,
    providers: list[str],
    panes: dict[str, str],
    created: list[str],
    *,
    root: str,
    percent: int,
    mark,
) -> None:
    if len(providers) == 2:
        assign_pane(
            backend,
            providers[1],
            panes,
            created,
            parent=root,
            direction="right",
            percent=percent,
            mark=mark,
        )
        return

    if len(providers) == 3:
        right_top = assign_pane(
            backend,
            providers[1],
            panes,
            created,
            parent=root,
            direction="right",
            percent=percent,
            mark=mark,
        )
        assign_pane(
            backend,
            providers[2],
            panes,
            created,
            parent=right_top,
            direction="bottom",
            percent=percent,
            mark=mark,
        )
        return

    right_top = assign_pane(
        backend,
        providers[1],
        panes,
        created,
        parent=root,
        direction="right",
        percent=percent,
        mark=mark,
    )
    assign_pane(
        backend,
        providers[2],
        panes,
        created,
        parent=root,
        direction="bottom",
        percent=percent,
        mark=mark,
    )
    assign_pane(
        backend,
        providers[3],
        panes,
        created,
        parent=right_top,
        direction="bottom",
        percent=percent,
        mark=mark,
    )


def assign_pane(
    backend: TmuxLayoutBackend,
    provider: str,
    panes: dict[str, str],
    created: list[str],
    *,
    parent: str,
    direction: str,
    percent: int,
    mark,
) -> str:
    pane_id = backend.split_pane(parent, direction, percent)
    created.append(pane_id)
    panes[provider] = pane_id
    mark(provider, pane_id)
    return pane_id


def build_layout_result(
    panes: dict[str, str],
    root: str,
    *,
    needs_attach: bool,
    created: list[str],
) -> LayoutResult:
    return LayoutResult(
        panes=panes,
        root_pane_id=root,
        needs_attach=needs_attach,
        created_panes=created,
    )
