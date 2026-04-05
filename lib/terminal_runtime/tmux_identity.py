from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TmuxPaneVisual:
    label_style: str
    border_style: str
    active_border_style: str


_CMD_VISUAL = TmuxPaneVisual(
    label_style='#[fg=#1e1e2e]#[bg=#7dcfff]#[bold]',
    border_style='fg=#7dcfff',
    active_border_style='fg=#7dcfff,bold',
)

_AGENT_VISUALS: tuple[TmuxPaneVisual, ...] = (
    TmuxPaneVisual(
        label_style='#[fg=#1e1e2e]#[bg=#ff9e64]#[bold]',
        border_style='fg=#ff9e64',
        active_border_style='fg=#ff9e64,bold',
    ),
    TmuxPaneVisual(
        label_style='#[fg=#1e1e2e]#[bg=#9ece6a]#[bold]',
        border_style='fg=#9ece6a',
        active_border_style='fg=#9ece6a,bold',
    ),
    TmuxPaneVisual(
        label_style='#[fg=#1e1e2e]#[bg=#f7768e]#[bold]',
        border_style='fg=#f7768e',
        active_border_style='fg=#f7768e,bold',
    ),
    TmuxPaneVisual(
        label_style='#[fg=#1e1e2e]#[bg=#e0af68]#[bold]',
        border_style='fg=#e0af68',
        active_border_style='fg=#e0af68,bold',
    ),
    TmuxPaneVisual(
        label_style='#[fg=#1e1e2e]#[bg=#bb9af7]#[bold]',
        border_style='fg=#bb9af7',
        active_border_style='fg=#bb9af7,bold',
    ),
    TmuxPaneVisual(
        label_style='#[fg=#1e1e2e]#[bg=#73daca]#[bold]',
        border_style='fg=#73daca',
        active_border_style='fg=#73daca,bold',
    ),
)


def pane_visual(*, order_index: int | None = None, is_cmd: bool = False) -> TmuxPaneVisual:
    if is_cmd:
        return _CMD_VISUAL
    index = max(0, int(order_index or 0))
    return _AGENT_VISUALS[index % len(_AGENT_VISUALS)]


def apply_ccb_pane_identity(
    backend,
    pane_id: str,
    *,
    title: str,
    agent_label: str,
    project_id: str,
    order_index: int | None = None,
    is_cmd: bool = False,
    slot_key: str | None = None,
    namespace_epoch: int | None = None,
    managed_by: str | None = 'ccbd',
) -> None:
    visual = pane_visual(order_index=order_index, is_cmd=is_cmd)
    backend.set_pane_title(pane_id, title)
    backend.set_pane_user_option(pane_id, '@ccb_label_style', visual.label_style)
    backend.set_pane_user_option(pane_id, '@ccb_border_style', visual.border_style)
    backend.set_pane_user_option(pane_id, '@ccb_active_border_style', visual.active_border_style)
    backend.set_pane_user_option(pane_id, '@ccb_agent', agent_label)
    backend.set_pane_user_option(pane_id, '@ccb_role', 'cmd' if is_cmd else 'agent')
    if slot_key:
        backend.set_pane_user_option(pane_id, '@ccb_slot', slot_key)
    if namespace_epoch is not None:
        backend.set_pane_user_option(pane_id, '@ccb_namespace_epoch', str(int(namespace_epoch)))
    if str(managed_by or '').strip():
        backend.set_pane_user_option(pane_id, '@ccb_managed_by', str(managed_by).strip())
    backend.set_pane_user_option(pane_id, '@ccb_project_id', project_id)
    setter = getattr(backend, 'set_pane_style', None)
    if callable(setter):
        setter(
            pane_id,
            border_style=visual.border_style,
            active_border_style=visual.active_border_style,
        )


__all__ = ['TmuxPaneVisual', 'apply_ccb_pane_identity', 'pane_visual']
