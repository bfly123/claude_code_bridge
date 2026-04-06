from __future__ import annotations

from pathlib import Path

from ..session import find_project_session_file as find_droid_project_session_file
from . import DROID_SESSIONS_ROOT, ensure_droid_watchdog_started, handle_droid_session_event


def _load_project_session(work_dir: Path):
    from ..session import load_project_session

    return load_project_session(work_dir)


def _load_bound_project_session(work_dir: Path, instance: str | None):
    from ..session import load_project_session

    return load_project_session(work_dir, instance)


def handle_project_droid_session_event(path: Path) -> None:
    handle_droid_session_event(
        path,
        find_project_session_file_fn=find_droid_project_session_file,
        load_project_session_fn=_load_bound_project_session,
    )


def ensure_project_droid_watchdog_started() -> None:
    ensure_droid_watchdog_started(
        root=DROID_SESSIONS_ROOT,
        find_project_session_file_fn=find_droid_project_session_file,
        load_project_session_fn=_load_bound_project_session,
    )


__all__ = ["ensure_project_droid_watchdog_started", "handle_project_droid_session_event"]
