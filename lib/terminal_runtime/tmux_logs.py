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
        pid = normalized_pane_id(pane_id)
        if not pid:
            return None
        try:
            return self.pane_log_path_for_fn(pid, 'tmux', self.socket_name)
        except Exception:
            return None

    def ensure_pane_log(self, pane_id: str) -> Path | None:
        pid = normalized_pane_id(pane_id)
        if not pid:
            return None
        log_path = self.pane_log_path(pid)
        if not log_path:
            return None
        prepare_log_path(log_path, cleanup_pane_logs_fn=self.cleanup_pane_logs_fn)
        if not pipe_pane_output(self, pid, log_path):
            return log_path
        trim_log_if_needed(log_path, maybe_trim_log_fn=self.maybe_trim_log_fn)
        record_pane_log_refresh(self.pane_log_info, pid, time_fn=self.time_fn)
        return log_path

    def refresh_pane_logs(self) -> None:
        info = self.pane_log_info
        if not isinstance(info, dict):
            return
        for pid in list(info.keys()):
            try:
                if not should_refresh_pane_log(self, pid):
                    continue
                self.ensure_pane_log(pid)
            except Exception:
                continue


def normalized_pane_id(pane_id: str) -> str:
    return (pane_id or '').strip()


def prepare_log_path(
    log_path: Path,
    *,
    cleanup_pane_logs_fn: Callable[[Path], None],
) -> None:
    try:
        cleanup_pane_logs_fn(log_path.parent)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.touch(exist_ok=True)
    except Exception:
        pass


def pipe_pane_output(manager: TmuxPaneLogManager, pane_id: str, log_path: Path) -> bool:
    try:
        manager.tmux_run_fn(
            ['pipe-pane', '-o', '-t', pane_id, f'tee -a {log_path}'],
            check=False,
        )
    except Exception:
        return False
    return True


def trim_log_if_needed(
    log_path: Path,
    *,
    maybe_trim_log_fn: Callable[[Path], None],
) -> None:
    try:
        maybe_trim_log_fn(log_path)
    except Exception:
        pass


def record_pane_log_refresh(
    pane_log_info: dict[str, float] | None,
    pane_id: str,
    *,
    time_fn: Callable[[], float],
) -> None:
    if pane_log_info is None:
        return
    try:
        pane_log_info[str(pane_id)] = time_fn()
    except Exception:
        pass


def should_refresh_pane_log(manager: TmuxPaneLogManager, pane_id: str) -> bool:
    if not manager.is_alive_fn(pane_id):
        return False
    return not pane_pipe_enabled(manager, pane_id)


def pane_pipe_enabled(manager: TmuxPaneLogManager, pane_id: str) -> bool:
    cp = manager.tmux_run_fn(
        ['display-message', '-p', '-t', pane_id, '#{pane_pipe}'],
        capture=True,
    )
    return manager.pane_pipe_enabled_fn(getattr(cp, 'stdout', '') or '')
