from __future__ import annotations

from .layouts_models import LayoutResult, TmuxLayoutBackend


def build_marker(
    backend: TmuxLayoutBackend,
    *,
    enabled: bool,
    marker_prefix: str,
):
    def mark(provider: str, pane_id: str) -> None:
        if not enabled:
            return
        backend.set_pane_title(pane_id, f'{marker_prefix}-{provider}')

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
            direction='right',
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
            direction='right',
            percent=percent,
            mark=mark,
        )
        assign_pane(
            backend,
            providers[2],
            panes,
            created,
            parent=right_top,
            direction='bottom',
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
        direction='right',
        percent=percent,
        mark=mark,
    )
    assign_pane(
        backend,
        providers[2],
        panes,
        created,
        parent=root,
        direction='bottom',
        percent=percent,
        mark=mark,
    )
    assign_pane(
        backend,
        providers[3],
        panes,
        created,
        parent=right_top,
        direction='bottom',
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


__all__ = [
    'build_layout_result',
    'build_marker',
    'build_split_layout',
]
