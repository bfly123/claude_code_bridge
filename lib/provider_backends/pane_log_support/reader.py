from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .reader_runtime import (
    capture_reader_state,
    latest_conversation_pairs,
    latest_reader_message,
    read_since_events,
    read_since_message,
    resolve_log_path,
    set_pane_log_path,
)


class PaneLogReaderBase:
    poll_env_var = 'CCB_PANE_LOG_POLL_INTERVAL'

    def __init__(self, work_dir: Optional[Path] = None, pane_log_path: Optional[Path] = None):
        self.work_dir = work_dir or Path.cwd()
        self._pane_log_path: Optional[Path] = pane_log_path
        try:
            poll = float(os.environ.get(self.poll_env_var, '0.05'))
        except Exception:
            poll = 0.05
        self._poll_interval = min(0.5, max(0.02, poll))

    def set_pane_log_path(self, path: Optional[Path]) -> None:
        set_pane_log_path(self, path)

    def _resolve_log_path(self) -> Optional[Path]:
        return resolve_log_path(self)

    def capture_state(self) -> Dict[str, Any]:
        return capture_reader_state(self)

    def wait_for_message(self, state: Dict[str, Any], timeout: float) -> Tuple[Optional[str], Dict[str, Any]]:
        return read_since_message(self, state, timeout=timeout, block=True)

    def try_get_message(self, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        return read_since_message(self, state, timeout=0.0, block=False)

    def wait_for_events(self, state: Dict[str, Any], timeout: float) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
        return read_since_events(self, state, timeout=timeout, block=True)

    def try_get_events(self, state: Dict[str, Any]) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
        return read_since_events(self, state, timeout=0.0, block=False)

    def latest_message(self) -> Optional[str]:
        return latest_reader_message(self)

    def latest_conversations(self, n: int = 1) -> List[Tuple[str, str]]:
        return latest_conversation_pairs(self, n=n)


__all__ = ['PaneLogReaderBase']
