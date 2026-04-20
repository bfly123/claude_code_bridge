from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from terminal_runtime.backend_env import apply_backend_env

from .polling import (
    read_new_entries as _read_new_entries_impl,
    read_new_events as _read_new_events_impl,
    read_new_messages as _read_new_messages_impl,
    read_since as _read_since_impl,
    read_since_events as _read_since_events_impl,
)
from .session_content import (
    capture_state as _capture_state_impl,
    latest_conversations as _latest_conversations_impl,
    latest_message as _latest_message_impl,
)
from .session_selection import (
    find_session_by_id as _find_session_by_id_impl,
    latest_session as _latest_session_impl,
    scan_latest_session as _scan_latest_session_impl,
    scan_latest_session_any_project as _scan_latest_session_any_project_impl,
    set_preferred_session as _set_preferred_session_impl,
    set_session_id_hint as _set_session_id_hint_impl,
)

apply_backend_env()


def default_sessions_root() -> Path:
    override = (os.environ.get("DROID_SESSIONS_ROOT") or os.environ.get("FACTORY_SESSIONS_ROOT") or "").strip()
    if override:
        return Path(override).expanduser()
    factory_home = (os.environ.get("FACTORY_HOME") or os.environ.get("FACTORY_ROOT") or "").strip()
    base = Path(factory_home).expanduser() if factory_home else (Path.home() / ".factory")
    return base / "sessions"


DROID_SESSIONS_ROOT = default_sessions_root()


class DroidLogReader:
    """Reads Droid session logs from ~/.factory/sessions"""

    def __init__(self, root: Path = DROID_SESSIONS_ROOT, work_dir: Optional[Path] = None):
        self.root = Path(root).expanduser()
        self.work_dir = work_dir or Path.cwd()
        self._preferred_session: Optional[Path] = None
        self._session_id_hint: Optional[str] = None
        try:
            poll = float(os.environ.get("DROID_POLL_INTERVAL", "0.05"))
        except Exception:
            poll = 0.05
        self._poll_interval = min(0.5, max(0.02, poll))
        try:
            limit = int(os.environ.get("DROID_SESSION_SCAN_LIMIT", "200"))
        except Exception:
            limit = 200
        self._scan_limit = max(1, limit)

    def set_preferred_session(self, session_path: Optional[Path]) -> None:
        _set_preferred_session_impl(self, session_path)

    def set_session_id_hint(self, session_id: Optional[str]) -> None:
        _set_session_id_hint_impl(self, session_id)

    def current_session_path(self) -> Optional[Path]:
        return self._latest_session()

    def _find_session_by_id(self) -> Optional[Path]:
        return _find_session_by_id_impl(self)

    def _scan_latest_session(self) -> Optional[Path]:
        return _scan_latest_session_impl(self)

    def _scan_latest_session_any_project(self) -> Optional[Path]:
        return _scan_latest_session_any_project_impl(self)

    def _latest_session(self) -> Optional[Path]:
        return _latest_session_impl(self)

    def capture_state(self) -> Dict[str, Any]:
        return _capture_state_impl(self)

    def wait_for_message(self, state: Dict[str, Any], timeout: float) -> Tuple[Optional[str], Dict[str, Any]]:
        return self._read_since(state, timeout=timeout, block=True)

    def try_get_message(self, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        return self._read_since(state, timeout=0.0, block=False)

    def wait_for_events(self, state: Dict[str, Any], timeout: float) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
        return self._read_since_events(state, timeout=timeout, block=True)

    def try_get_events(self, state: Dict[str, Any]) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
        return self._read_since_events(state, timeout=0.0, block=False)

    def latest_message(self) -> Optional[str]:
        return _latest_message_impl(self)

    def latest_conversations(self, n: int = 1) -> List[Tuple[str, str]]:
        return _latest_conversations_impl(self, n)

    def _read_since(self, state: Dict[str, Any], timeout: float, block: bool) -> Tuple[Optional[str], Dict[str, Any]]:
        return _read_since_impl(self, state, timeout, block)

    def _read_new_messages(self, session: Path, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        return _read_new_messages_impl(session, state)

    def _read_since_events(self, state: Dict[str, Any], timeout: float, block: bool) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
        return _read_since_events_impl(self, state, timeout, block)

    def _read_new_events(self, session: Path, state: Dict[str, Any]) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
        return _read_new_events_impl(session, state)


def _read_new_entries(session: Path, state: Dict[str, object]) -> Tuple[List[dict[str, object]], Dict[str, object]]:
    return _read_new_entries_impl(session, state)


__all__ = ['DROID_SESSIONS_ROOT', 'DroidLogReader', 'default_sessions_root']
