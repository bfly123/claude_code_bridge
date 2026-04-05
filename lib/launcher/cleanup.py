from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class LauncherCleanupCoordinator:
    ccb_pid: int
    project_session_paths: tuple[Path, ...]
    mark_session_inactive_fn: Callable[..., None]
    safe_write_session_fn: Callable[..., tuple[bool, str | None]]

    def mark_project_sessions_inactive(self) -> None:
        for session_file in self.project_session_paths:
            if not session_file.exists():
                continue
            try:
                self.mark_session_inactive_fn(session_file, safe_write_session_fn=self.safe_write_session_fn)
            except Exception:
                pass

    def shutdown_owned_ccbd(self) -> None:
        # Project-scoped ccbd ownership is handled by the CLI/keeper contract.
        # The legacy launcher cleanup path must not infer backend ownership from
        # obsolete standalone daemon state files.
        return None
