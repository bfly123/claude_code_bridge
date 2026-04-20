from __future__ import annotations

from pathlib import Path

from terminal_runtime.backend_env import apply_backend_env

from .comm_runtime import (
    DROID_SESSIONS_ROOT,
    DroidLogReader,
    find_droid_session_file,
    load_droid_session_info,
    publish_droid_registry,
    read_droid_session_start,
    remember_droid_session_binding,
)
from .comm_runtime.communicator_facade import DroidCommunicator
from .comm_runtime.watchdog_facade import (
    ensure_project_droid_watchdog_started as _ensure_project_droid_watchdog_started,
    handle_project_droid_session_event as _handle_project_droid_session_event,
)
from .session import find_project_session_file as find_droid_project_session_file

apply_backend_env()

def _handle_droid_session_event(path: Path) -> None:
    _handle_project_droid_session_event(path)


def _ensure_droid_watchdog_started() -> None:
    _ensure_project_droid_watchdog_started()


_ensure_droid_watchdog_started()


__all__ = [
    'DROID_SESSIONS_ROOT',
    'DroidCommunicator',
    'DroidLogReader',
    'find_droid_project_session_file',
    'read_droid_session_start',
]
