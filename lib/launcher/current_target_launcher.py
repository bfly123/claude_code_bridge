from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TextIO


@dataclass
class LauncherCurrentTargetLauncher:
    bind_current_pane_fn: Callable[..., str | None]
    stderr: TextIO = sys.stderr

    def bind_target(
        self,
        *,
        runtime: Path,
        pane_title_marker: str,
        agent_label: str,
        bind_session_fn: Callable[[str], bool],
        display_label: str,
    ) -> str | None:
        pane_id = self.bind_current_pane_fn(
            runtime=runtime,
            pane_title_marker=pane_title_marker,
            agent_label=agent_label,
            bind_session_fn=bind_session_fn,
        )
        if not pane_id:
            print(f'❌ Unable to determine current pane id for {display_label}', file=self.stderr)
            return None
        return pane_id

    def start_shell_target(
        self,
        *,
        runtime: Path,
        pane_title_marker: str,
        agent_label: str,
        display_label: str,
        bind_session_fn: Callable[[str], bool],
        start_cmd: str,
        run_shell_command_fn: Callable[..., int],
        cwd: str,
    ) -> int:
        pane_id = self.bind_target(
            runtime=runtime,
            pane_title_marker=pane_title_marker,
            agent_label=agent_label,
            bind_session_fn=bind_session_fn,
            display_label=display_label,
        )
        if not pane_id:
            return 1
        return run_shell_command_fn(start_cmd, cwd=cwd)
