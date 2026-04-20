from __future__ import annotations

from .layouts_models import LayoutResult, TmuxLayoutBackend
from .layouts_root import resolve_root_pane
from .layouts_split import build_layout_result, build_marker, build_split_layout


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
