from __future__ import annotations

from pathlib import Path
from typing import Any

from . import (
    capture_state as _capture_reader_state,
    debug_enabled as _debug_enabled,
    debug_log_reader as _debug_log_reader,
    extract_last_gemini as _extract_last_gemini_impl,
    initialize_reader as _initialize_reader,
    latest_conversations as _latest_conversations_impl,
    latest_message as _latest_message_impl,
    latest_session as _latest_session_impl,
    read_session_json as _read_session_json_impl,
    read_since as _read_since_impl,
    scan_latest_session as _scan_latest_session_impl,
    scan_latest_session_any_project as _scan_latest_session_any_project_impl,
    session_belongs_to_current_project as _session_belongs_to_current_project_impl,
    set_preferred_session as _set_preferred_session_impl,
)
from .paths import GEMINI_ROOT


class GeminiLogReader:
    """Reads Gemini session files from ~/.gemini/tmp/<hash>/chats."""

    def __init__(self, root: Path = GEMINI_ROOT, work_dir: Path | None = None):
        _initialize_reader(self, root=root, work_dir=work_dir)

    def _session_belongs_to_current_project(self, session_path: Path) -> bool:
        return _session_belongs_to_current_project_impl(self, session_path)

    @staticmethod
    def _debug_enabled() -> bool:
        return _debug_enabled()

    @classmethod
    def _debug(cls, message: str) -> None:
        _debug_log_reader(message)

    def _scan_latest_session_any_project(self) -> Path | None:
        """Scan latest session across all project hashes as a fallback."""
        return _scan_latest_session_any_project_impl(self)

    def _scan_latest_session(self) -> Path | None:
        return _scan_latest_session_impl(self)

    def _latest_session(self) -> Path | None:
        return _latest_session_impl(self)

    def set_preferred_session(self, session_path: Path | None) -> None:
        _set_preferred_session_impl(self, session_path)

    def current_session_path(self) -> Path | None:
        return self._latest_session()

    def _read_session_json(self, session: Path) -> dict[str, Any] | None:
        return _read_session_json_impl(self, session)

    def capture_state(self) -> dict[str, Any]:
        return _capture_reader_state(self)

    def wait_for_message(self, state: dict[str, Any], timeout: float) -> tuple[str | None, dict[str, Any]]:
        return self._read_since(state, timeout, block=True)

    def try_get_message(self, state: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
        return self._read_since(state, timeout=0.0, block=False)

    def latest_message(self) -> str | None:
        return _latest_message_impl(self)

    def latest_conversations(self, n: int = 1) -> list[tuple[str, str]]:
        return _latest_conversations_impl(self, n)

    def _read_since(self, state: dict[str, Any], timeout: float, block: bool) -> tuple[str | None, dict[str, Any]]:
        return _read_since_impl(self, state, timeout, block)

    @staticmethod
    def _extract_last_gemini(payload: dict[str, Any]) -> tuple[str | None, str] | None:
        return _extract_last_gemini_impl(payload)


__all__ = ["GeminiLogReader"]
