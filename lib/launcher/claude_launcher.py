from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from terminal_runtime import TmuxBackend

from launcher.tmux_helpers import label_tmux_pane


@dataclass
class LauncherClaudePaneLauncher:
    script_dir: object
    tmux_panes: dict[str, str]
    build_env_prefix_fn: Callable[[dict], str]
    export_path_builder_fn: Callable[[object], str]
    pane_title_builder_fn: Callable[[str], str]
    tmux_backend_factory: Callable[[], object] = TmuxBackend
    label_tmux_pane_fn: Callable[..., None] = label_tmux_pane

    def start(
        self,
        *,
        run_cwd: str,
        start_cmd: str,
        env_overrides: dict,
        write_local_session_fn: Callable[..., None],
        read_local_session_id_fn: Callable[[], str | None],
        parent_pane: str | None,
        direction: str | None,
        display_label: str = 'Claude',
    ) -> str | None:
        script_dir = Path(self.script_dir)
        label = str(display_label or '').strip() or 'Claude'
        pane_title_marker = f'CCB-{label}'
        full_cmd = (
            self.pane_title_builder_fn(pane_title_marker)
            + self.build_env_prefix_fn(env_overrides)
            + self.export_path_builder_fn(script_dir / 'bin')
            + start_cmd
        )
        use_direction = (direction or 'right').strip() or 'right'
        use_parent = parent_pane

        backend = self.tmux_backend_factory()
        pane_id = backend.create_pane('', run_cwd, direction=use_direction, percent=50, parent_pane=use_parent)
        backend.respawn_pane(pane_id, cmd=full_cmd, cwd=run_cwd, remain_on_exit=True)
        self.label_tmux_pane_fn(backend, pane_id, title=pane_title_marker, agent_label=label)
        self.tmux_panes['claude'] = pane_id

        try:
            write_local_session_fn(
                session_id=read_local_session_id_fn(),
                active=True,
                pane_id=str(pane_id or ''),
                pane_title_marker=pane_title_marker,
                terminal='tmux',
            )
        except Exception:
            pass
        return pane_id
