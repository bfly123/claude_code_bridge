from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Optional

from provider_core.session_binding_runtime import resolve_bound_instance
from provider_sessions.watch import HAS_WATCHDOG, SessionFileWatcher
from terminal_runtime.backend_env import apply_backend_env

from .log_reader import DROID_SESSIONS_ROOT
from .parsing import read_droid_session_start

apply_backend_env()

_DROID_WATCHER: Optional[SessionFileWatcher] = None
_DROID_WATCH_STARTED = False
_DROID_WATCH_LOCK = threading.Lock()


def handle_droid_session_event(
    path: Path,
    *,
    find_project_session_file_fn: Callable[[Path, str | None], Optional[Path]],
    load_project_session_fn: Callable[[Path, str | None], object | None],
) -> None:
    if not path or not path.exists() or path.suffix != ".jsonl":
        return
    cwd, session_id = read_droid_session_start(path)
    if not cwd:
        return
    try:
        work_dir = Path(cwd).expanduser()
    except Exception:
        return
    instance = resolve_bound_instance(
        provider="droid",
        base_filename=".droid-session",
        work_dir=work_dir,
        allow_env=False,
    )
    session_file = find_project_session_file_fn(work_dir, instance)
    if not session_file or not session_file.exists():
        return
    session = load_project_session_fn(work_dir, instance)
    if not session:
        return
    try:
        session.update_droid_binding(session_path=path, session_id=session_id)
    except Exception:
        return


def ensure_droid_watchdog_started(
    *,
    root: Path = DROID_SESSIONS_ROOT,
    watcher_factory: Callable[..., SessionFileWatcher] = SessionFileWatcher,
    find_project_session_file_fn: Callable[[Path, str | None], Optional[Path]],
    load_project_session_fn: Callable[[Path, str | None], object | None],
) -> None:
    if not HAS_WATCHDOG:
        return
    global _DROID_WATCHER, _DROID_WATCH_STARTED
    if _DROID_WATCH_STARTED:
        return
    with _DROID_WATCH_LOCK:
        if _DROID_WATCH_STARTED:
            return
        if not root.exists():
            return
        watcher = watcher_factory(
            root,
            lambda path: handle_droid_session_event(
                path,
                find_project_session_file_fn=find_project_session_file_fn,
                load_project_session_fn=load_project_session_fn,
            ),
            recursive=True,
        )
        try:
            watcher.start()
        except Exception:
            return
        _DROID_WATCHER = watcher
        _DROID_WATCH_STARTED = True


__all__ = ['ensure_droid_watchdog_started', 'handle_droid_session_event']
