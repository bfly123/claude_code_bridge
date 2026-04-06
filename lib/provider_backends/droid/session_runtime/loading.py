from __future__ import annotations

from pathlib import Path

from provider_backends.pane_log_support.session import compute_session_key_for_provider

from .model import DroidProjectSession
from .pathing import find_project_session_file, read_json


def load_project_session(work_dir: Path, instance: str | None = None) -> DroidProjectSession | None:
    session_file = find_project_session_file(work_dir, instance)
    if not session_file:
        return None
    data = read_json(session_file)
    if not data or data.get("active") is False:
        return None
    return DroidProjectSession(session_file=session_file, data=data)


def compute_session_key(session: DroidProjectSession, instance: str | None = None) -> str:
    return compute_session_key_for_provider(session, provider="droid", instance=instance)


__all__ = ["compute_session_key", "load_project_session"]
