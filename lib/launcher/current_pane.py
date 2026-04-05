from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from terminal_runtime import TmuxBackend

from launcher.tmux_helpers import label_tmux_pane


@dataclass
class LauncherCurrentPaneBinder:
    terminal_type: str | None
    current_pane_id_fn: Callable[[], str]
    backend_factory: Callable[[], object] = TmuxBackend
    label_tmux_pane_fn: Callable[..., None] = label_tmux_pane

    def bind(
        self,
        *,
        runtime: Path,
        pane_title_marker: str,
        agent_label: str,
        bind_session_fn: Callable[[str], bool],
    ) -> str | None:
        runtime.mkdir(parents=True, exist_ok=True)
        pane_id = (self.current_pane_id_fn() or '').strip()
        if not pane_id:
            return None
        if self.terminal_type == 'tmux':
            try:
                backend = self.backend_factory()
                self.label_tmux_pane_fn(backend, pane_id, title=pane_title_marker, agent_label=agent_label)
            except Exception:
                pass
        bind_session_fn(pane_id)
        return pane_id
