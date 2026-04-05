from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from provider_sessions.files import find_project_session_file
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
    if not path or not path.exists():
        return
    payload = read_opencode_session_json(path)
    if not isinstance(payload, dict):
        return
    directory = payload.get("directory")
    if not isinstance(directory, str) or not directory.strip():
        return
    try:
        work_dir = Path(directory.strip()).expanduser()
    except Exception:
        return
    session_file = find_project_session_file(work_dir, ".opencode-session")
    if not session_file or not session_file.exists():
        return
    session_id = payload.get("id") if isinstance(payload.get("id"), str) else None
    project_id = path.parent.name if path.parent else ""
    try:
        from provider_backends.opencode.session import load_project_session
    except Exception:
        return
    session = load_project_session(work_dir)
    if not session:
        return
    try:
        session.update_opencode_binding(session_id=session_id, project_id=project_id)
    except Exception:
        return


def ensure_opencode_watchdog_started() -> None:
    if not HAS_WATCHDOG:
        return
    global _OPENCODE_WATCHER, _OPENCODE_WATCH_STARTED
    if _OPENCODE_WATCH_STARTED:
        return
    with _OPENCODE_WATCH_LOCK:
        if _OPENCODE_WATCH_STARTED:
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
