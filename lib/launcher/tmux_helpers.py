from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path


def choose_tmux_split_target(
    backend,
    *,
    existing_panes: Mapping[str, str],
    direction: str | None,
    parent_pane: str | None,
) -> tuple[str, str | None]:
    use_direction = (direction or ('right' if not existing_panes else 'bottom')).strip() or 'right'
    use_parent = parent_pane
    if not use_parent:
        try:
            use_parent = backend.get_current_pane_id()
        except Exception:
            use_parent = None
    if not use_parent and use_direction == 'bottom':
        try:
            use_parent = next(reversed(existing_panes.values()))
        except StopIteration:
            use_parent = None
    try:
        if use_parent and str(use_parent).startswith('%') and not backend.pane_exists(str(use_parent)):
            use_parent = backend.get_current_pane_id()
    except Exception:
        use_parent = None
    return use_direction, use_parent


def label_tmux_pane(backend, pane_id: str, *, title: str, agent_label: str) -> None:
    backend.set_pane_title(pane_id, title)
    backend.set_pane_user_option(pane_id, '@ccb_agent', agent_label)


def spawn_tmux_pane(
    backend,
    *,
    cwd: Path,
    cmd: str,
    title: str,
    agent_label: str,
    existing_panes: Mapping[str, str],
    direction: str | None,
    parent_pane: str | None,
) -> str:
    use_direction, use_parent = choose_tmux_split_target(
        backend,
        existing_panes=existing_panes,
        direction=direction,
        parent_pane=parent_pane,
    )
    pane_id = backend.create_pane('', str(cwd), direction=use_direction, percent=50, parent_pane=use_parent)
    backend.respawn_pane(pane_id, cmd=cmd, cwd=str(cwd), remain_on_exit=True)
    label_tmux_pane(backend, pane_id, title=title, agent_label=agent_label)
    return pane_id
