from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class LauncherCmdPaneLauncher:
    extra_panes: dict[str, str]
    backend_factory: Callable[[], object]
    label_tmux_pane_fn: Callable[..., None]
    print_fn: Callable[[str], None] = print

    def start(
        self,
        *,
        title: str,
        full_cmd: str,
        cwd: str,
        parent_pane: str | None,
        direction: str | None,
    ) -> str:
        use_direction = (direction or 'right').strip() or 'right'
        use_parent = parent_pane

        backend = self.backend_factory()
        pane_id = backend.create_pane('', cwd, direction=use_direction, percent=50, parent_pane=use_parent)
        backend.respawn_pane(pane_id, cmd=full_cmd, cwd=cwd, remain_on_exit=True)
        self.label_tmux_pane_fn(backend, pane_id, title=title, agent_label='Cmd')

        self.extra_panes['cmd'] = pane_id
        self.print_fn(f'✅ Started cmd pane ({pane_id})')
        return pane_id
