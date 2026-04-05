from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class LauncherTargetTmuxStarter:
    start_simple_target_fn: Callable[..., str]
    print_fn: Callable[[str], None] = print

    def start(
        self,
        *,
        target_key: str,
        display_label: str,
        runtime: Path,
        cwd: Path,
        start_cmd: str,
        pane_title_marker: str,
        agent_label: str,
        parent_pane: str | None,
        direction: str | None,
        write_session_fn: Callable[..., bool],
        started_backend_text: str,
    ) -> str:
        pane_id = self.start_simple_target_fn(
            target_key=target_key,
            runtime=runtime,
            cwd=cwd,
            start_cmd=start_cmd,
            pane_title_marker=pane_title_marker,
            agent_label=agent_label,
            parent_pane=parent_pane,
            direction=direction,
            write_session_fn=write_session_fn,
        )
        self.print_fn(
            started_backend_text.format(
                label=display_label,
                provider=display_label,
                pane_id=pane_id,
            )
        )
        return pane_id
