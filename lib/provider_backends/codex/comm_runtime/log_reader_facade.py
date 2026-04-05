from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import (
    capture_log_reader_state as _capture_log_reader_state,
    debug_enabled as _debug_enabled,
    debug_log_reader as _debug_log_reader,
    env_int as _env_int_impl,
    extract_cwd_from_log as _extract_cwd_from_log_impl,
    iter_lines_reverse as _iter_lines_reverse_impl,
    latest_conversations as _latest_conversations_impl,
    latest_log as _latest_log_impl,
    latest_message as _latest_message_impl,
    normalize_path as _normalize_path_impl,
    normalize_work_dir as _normalize_work_dir_impl,
    read_entry_since as _read_entry_since_impl,
    read_event_since as _read_event_since_impl,
    read_since as _read_since_impl,
    scan_latest as _scan_latest_impl,
)
from .paths import SESSION_ROOT


class CodexLogReader:
    """Reads Codex official logs from ~/.codex/sessions."""

    def __init__(
        self,
        root: Path = SESSION_ROOT,
        log_path: Path | None = None,
        session_id_filter: str | None = None,
        work_dir: Path | None = None,
        follow_workspace_sessions: bool = False,
    ):
        self.root = Path(root).expanduser()
        self._preferred_log = self._normalize_path(log_path)
        self._session_id_filter = session_id_filter
        self._work_dir = self._normalize_work_dir(work_dir)
        self._follow_workspace_sessions = bool(follow_workspace_sessions and self._work_dir)
        try:
            poll = float(os.environ.get("CODEX_POLL_INTERVAL", "0.05"))
        except Exception:
            poll = 0.05
        self._poll_interval = min(0.5, max(0.01, poll))

    @staticmethod
    def _debug_enabled() -> bool:
        return _debug_enabled()

    @classmethod
    def _debug(cls, message: str) -> None:
        _debug_log_reader(message)

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        return _env_int_impl(name, default)

    def _iter_lines_reverse(self, log_path: Path, *, max_bytes: int, max_lines: int) -> list[str]:
        return _iter_lines_reverse_impl(self, log_path, max_bytes=max_bytes, max_lines=max_lines)

    def set_preferred_log(self, log_path: Path | None) -> None:
        self._preferred_log = self._normalize_path(log_path)

    def _normalize_work_dir(self, work_dir: Path | None) -> str | None:
        return _normalize_work_dir_impl(work_dir)

    def _extract_cwd_from_log(self, log_path: Path) -> str | None:
        return _extract_cwd_from_log_impl(self, log_path)

    def _normalize_path(self, value: Any | None) -> Path | None:
        return _normalize_path_impl(value)

    def _scan_latest(self) -> Path | None:
        return _scan_latest_impl(self)

    def _latest_log(self) -> Path | None:
        return _latest_log_impl(self)

    def current_log_path(self) -> Path | None:
        return self._latest_log()

    def capture_state(self) -> dict[str, Any]:
        return _capture_log_reader_state(self)

    def wait_for_message(self, state: dict[str, Any], timeout: float) -> tuple[str | None, dict[str, Any]]:
        return self._read_since(state, timeout, block=True)

    def try_get_message(self, state: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
        return self._read_since(state, timeout=0.0, block=False)

    def wait_for_event(
        self, state: dict[str, Any], timeout: float
    ) -> tuple[tuple[str, str] | None, dict[str, Any]]:
        return self._read_event_since(state, timeout, block=True)

    def try_get_event(self, state: dict[str, Any]) -> tuple[tuple[str, str] | None, dict[str, Any]]:
        return self._read_event_since(state, timeout=0.0, block=False)

    def wait_for_entries(self, state: dict[str, Any], timeout: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        entry, new_state = self._read_entry_since(state, timeout, block=True)
        if entry is None:
            return [], new_state
        return [entry], new_state

    def try_get_entries(self, state: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        entry, new_state = self._read_entry_since(state, timeout=0.0, block=False)
        if entry is None:
            return [], new_state
        return [entry], new_state

    def latest_message(self) -> str | None:
        return _latest_message_impl(self)

    def _read_since(self, state: dict[str, Any], timeout: float, block: bool) -> tuple[str | None, dict[str, Any]]:
        return _read_since_impl(self, state, timeout, block)

    def _read_event_since(
        self, state: dict[str, Any], timeout: float, block: bool
    ) -> tuple[tuple[str, str] | None, dict[str, Any]]:
        return _read_event_since_impl(self, state, timeout, block)

    def _read_entry_since(
        self, state: dict[str, Any], timeout: float, block: bool
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        return _read_entry_since_impl(self, state, timeout, block)

    def latest_conversations(self, n: int = 1) -> list[tuple[str, str]]:
        return _latest_conversations_impl(self, n)


__all__ = ["CodexLogReader"]
