from __future__ import annotations

from dataclasses import dataclass
import hashlib


@dataclass(frozen=True)
class TmuxPaneVisual:
    label_style: str
    border_style: str
    active_border_style: str

def _visual(*, bg: str, border: str | None = None, active: str | None = None, fg: str = '#16161e') -> TmuxPaneVisual:
    border_color = str(border or bg).strip()
    active_color = str(active or border_color).strip()
    return TmuxPaneVisual(
        label_style=f'#[fg={fg}]#[bg={bg}]#[bold]',
        border_style=f'fg={border_color}',
        active_border_style=f'fg={active_color},bold',
    )


_CMD_VISUALS: tuple[TmuxPaneVisual, ...] = (
    _visual(bg='#7dcfff', border='#5fb3d6', active='#7dcfff'),
    _visual(bg='#73daca', border='#4fb7a9', active='#73daca'),
    _visual(bg='#89b4fa', border='#6b8fd6', active='#89b4fa'),
    _visual(bg='#2ac3de', border='#1b9fb8', active='#2ac3de'),
)

_AGENT_VISUALS: tuple[TmuxPaneVisual, ...] = (
    _visual(bg='#ff9e64', border='#d9824f', active='#ff9e64'),
    _visual(bg='#9ece6a', border='#7ca952', active='#9ece6a'),
    _visual(bg='#f7768e', border='#d85f78', active='#f7768e'),
    _visual(bg='#e0af68', border='#bd8d4f', active='#e0af68'),
    _visual(bg='#bb9af7', border='#9d7fda', active='#bb9af7'),
    _visual(bg='#73daca', border='#54bda7', active='#73daca'),
    _visual(bg='#7aa2f7', border='#5d82d6', active='#7aa2f7'),
    _visual(bg='#f6bd60', border='#d69f46', active='#f6bd60'),
    _visual(bg='#ff757f', border='#da5a66', active='#ff757f'),
    _visual(bg='#8bd5ca', border='#68b6aa', active='#8bd5ca'),
    _visual(bg='#c6a0f6', border='#a885d8', active='#c6a0f6'),
    _visual(bg='#a6da95', border='#84b777', active='#a6da95'),
    TmuxPaneVisual(
        label_style='#[fg=#16161e]#[bg=#f5bde6]#[bold]',
        border_style='fg=#d49ac5',
        active_border_style='fg=#f5bde6,bold',
    ),
)


def pane_visual(
    *,
    project_id: str | None = None,
    slot_key: str | None = None,
    order_index: int | None = None,
    is_cmd: bool = False,
) -> TmuxPaneVisual:
    if is_cmd:
        return _select_visual(_CMD_VISUALS, project_id=project_id, slot_key=slot_key, fallback_index=order_index)
    return _select_visual(_AGENT_VISUALS, project_id=project_id, slot_key=slot_key, fallback_index=order_index)


def _select_visual(
    visuals: tuple[TmuxPaneVisual, ...],
    *,
    project_id: str | None,
    slot_key: str | None,
    fallback_index: int | None,
) -> TmuxPaneVisual:
    if project_id and slot_key:
        key = f'{project_id}:{slot_key}'
        return visuals[_stable_index(key, len(visuals))]
    index = max(0, int(order_index or 0))
    return visuals[index % len(visuals)]


def _stable_index(key: str, size: int) -> int:
    if size <= 0:
        return 0
    digest = hashlib.sha256(str(key or '').encode('utf-8')).hexdigest()
    return int(digest[:8], 16) % size


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
    visual = pane_visual(
        project_id=project_id,
        slot_key=slot_key or title,
        order_index=order_index,
        is_cmd=is_cmd,
    )
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
