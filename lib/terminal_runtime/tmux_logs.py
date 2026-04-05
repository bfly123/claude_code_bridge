from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class TmuxPaneLogManager:
    socket_name: str | None
    tmux_run_fn: Callable[..., object]
    is_alive_fn: Callable[[str], bool]
    pane_pipe_enabled_fn: Callable[[str], bool]
    pane_log_path_for_fn: Callable[[str, str, str | None], Path]
    cleanup_pane_logs_fn: Callable[[Path], None]
    maybe_trim_log_fn: Callable[[Path], None]
    time_fn: Callable[[], float] = time.time
    pane_log_info: dict[str, float] | None = None

    def pane_log_path(self, pane_id: str) -> Path | None:
        pid = (pane_id or '').strip()
        if not pid:
            return None
        try:
            return self.pane_log_path_for_fn(pid, 'tmux', self.socket_name)
        except Exception:
            return None

    def ensure_pane_log(self, pane_id: str) -> Path | None:
        pid = (pane_id or '').strip()
        if not pid:
            return None
        log_path = self.pane_log_path(pid)
        if not log_path:
            return None
        try:
            self.cleanup_pane_logs_fn(log_path.parent)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.touch(exist_ok=True)
        except Exception:
            pass
        try:
            self.tmux_run_fn(['pipe-pane', '-o', '-t', pid, f'tee -a {log_path}'], check=False)
        except Exception:
            return log_path
        try:
            self.maybe_trim_log_fn(log_path)
        except Exception:
            pass
        info = self.pane_log_info
        if info is not None:
            try:
                info[str(pid)] = self.time_fn()
            except Exception:
                pass
        return log_path

    def refresh_pane_logs(self) -> None:
        info = self.pane_log_info
        if not isinstance(info, dict):
            return
        for pid in list(info.keys()):
            try:
                if not self.is_alive_fn(pid):
                    continue
                cp = self.tmux_run_fn(['display-message', '-p', '-t', pid, '#{pane_pipe}'], capture=True)
                if self.pane_pipe_enabled_fn(getattr(cp, 'stdout', '') or ''):
                    continue
                self.ensure_pane_log(pid)
            except Exception:
                continue
