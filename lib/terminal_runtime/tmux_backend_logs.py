from __future__ import annotations

from pathlib import Path
from typing import Optional

from terminal_runtime.tmux_logs import TmuxPaneLogManager


class TmuxBackendLogsMixin:
    def pane_log_path(self, pane_id: str) -> Optional[Path]:
        return self._services.pane_log_manager.pane_log_path(pane_id)

    def ensure_pane_log(self, pane_id: str) -> Optional[Path]:
        return self._services.pane_log_manager.ensure_pane_log(pane_id)

    def refresh_pane_logs(self) -> None:
        self._services.pane_log_manager.refresh_pane_logs()

    def _pane_log_manager(self) -> TmuxPaneLogManager:
        return self._services.pane_log_manager


__all__ = ['TmuxBackendLogsMixin']
