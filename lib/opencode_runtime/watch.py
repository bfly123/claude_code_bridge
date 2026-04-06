from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from provider_core.session_binding_runtime import resolve_bound_instance
from provider_sessions.watch import HAS_WATCHDOG, SessionFileWatcher

from .paths import OPENCODE_STORAGE_ROOT

_OPENCODE_WATCHER: SessionFileWatcher | None = None
_OPENCODE_WATCH_STARTED = False
_OPENCODE_WATCH_LOCK = threading.Lock()


def opencode_watch_predicate(path: Path) -> bool:
    return path.suffix == ".json" and path.name.startswith("ses_")


def read_opencode_session_json(path: Path) -> dict | None:
    if not path or not path.exists():
        return None
    for _ in range(5):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            time.sleep(0.05)
            continue
        except Exception:
            return None
    return None


def handle_opencode_session_event(path: Path) -> None:
    if not is_existing_session_path(path):
        return
    payload = read_opencode_session_json(path)
    if not isinstance(payload, dict):
        return
    work_dir = payload_work_dir(payload)
    if work_dir is None:
        return
    session_id = payload_session_id(payload)
    project_id = payload_project_id(path)
    try:
        from provider_backends.opencode.session import find_project_session_file, load_project_session
    except Exception:
        return
    instance = resolve_bound_instance(
        provider="opencode",
        base_filename=".opencode-session",
        work_dir=work_dir,
        allow_env=False,
    )
    session_file = find_project_session_file(work_dir, instance)
    if not session_file or not session_file.exists():
        return
    session = load_project_session(work_dir, instance)
    if not session:
        return
    try:
        session.update_opencode_binding(session_id=session_id, project_id=project_id)
    except Exception:
        return


def ensure_opencode_watchdog_started() -> None:
    global _OPENCODE_WATCHER, _OPENCODE_WATCH_STARTED
    if not should_start_watchdog():
        return
    with _OPENCODE_WATCH_LOCK:
        if not should_start_watchdog():
            return
        sessions_root = OPENCODE_STORAGE_ROOT / "session"
        if not sessions_root.exists():
            return
        watcher = SessionFileWatcher(
            sessions_root,
            handle_opencode_session_event,
            recursive=True,
            predicate=opencode_watch_predicate,
        )
        try:
            watcher.start()
        except Exception:
            return
        _OPENCODE_WATCHER = watcher
        _OPENCODE_WATCH_STARTED = True


def is_existing_session_path(path: Path | None) -> bool:
    return bool(path and path.exists())


def payload_work_dir(payload: dict) -> Path | None:
    directory = payload.get("directory")
    if not isinstance(directory, str) or not directory.strip():
        return None
    try:
        return Path(directory.strip()).expanduser()
    except Exception:
        return None


def payload_session_id(payload: dict) -> str | None:
    session_id = payload.get("id")
    return session_id if isinstance(session_id, str) else None


def payload_project_id(path: Path) -> str:
    return path.parent.name if path.parent else ""


def should_start_watchdog() -> bool:
    return bool(HAS_WATCHDOG and not _OPENCODE_WATCH_STARTED)
