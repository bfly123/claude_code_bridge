from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from provider_backends.claude.registry_support.logs import (
    env_float as _env_float,
    env_int as _env_int,
    refresh_claude_log_binding as _refresh_claude_log_binding,
)
from provider_backends.claude.registry_support.pathing import (
    candidate_project_dirs as _candidate_project_dirs,
)
from provider_backends.claude.session import ClaudeProjectSession
from provider_sessions.watch import HAS_WATCHDOG, SessionFileWatcher

from . import (
    SessionEntry as _SessionEntry,
    WatcherEntry as _WatcherEntry,
    check_all_sessions as _check_all_sessions_impl,
    check_one as _check_one_impl,
    ensure_watchers_for_work_dir as _ensure_watchers_for_work_dir_impl,
    get_session as _get_session_impl,
    handle_new_log_file,
    handle_new_log_file_global,
    handle_sessions_index,
    invalidate as _invalidate_impl,
    load_and_cache as _load_and_cache_impl,
    monitor_loop as _monitor_loop_impl,
    project_dirs_for_work_dir as _project_dirs_for_work_dir_impl,
    read_log_meta_with_retry,
    register_session as _register_session_impl,
    release_watchers_for_work_dir as _release_watchers_for_work_dir_impl,
    remove as _remove_impl,
    start_monitor as _start_monitor_impl,
    start_root_watcher as _start_root_watcher_impl,
    stop_all_watchers as _stop_all_watchers_impl,
    stop_monitor as _stop_monitor_impl,
    stop_root_watcher as _stop_root_watcher_impl,
    update_session_file_direct,
)
from .binding_runtime import find_claude_session_file, load_claude_session
from .logging import write_registry_log
from .settings import CLAUDE_PROJECTS_ROOT


class ClaudeSessionRegistry:
    """Manages and monitors all active Claude sessions."""

    CHECK_INTERVAL = 10.0

    def __init__(self, *, claude_root: Path = CLAUDE_PROJECTS_ROOT):
        self._lock = threading.Lock()
        self._sessions: dict[str, _SessionEntry] = {}
        self._stop = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._claude_root = claude_root
        self._watchers: dict[str, _WatcherEntry] = {}
        self._root_watcher: Optional[SessionFileWatcher] = None
        self._pending_logs: dict[str, float] = {}
        self._log_last_check: dict[str, float] = {}
        self._session_entry_cls = _SessionEntry
        self._watcher_entry_cls = _WatcherEntry

    def start_monitor(self) -> None:
        _start_monitor_impl(self)

    def stop_monitor(self) -> None:
        _stop_monitor_impl(self)

    def get_session(self, work_dir: Path) -> Optional[ClaudeProjectSession]:
        return _get_session_impl(
            self,
            work_dir,
            find_session_file_fn=self._find_claude_session_file,
            write_log_fn=write_registry_log,
            load_and_cache_fn=self._load_and_cache,
        )

    def register_session(self, work_dir: Path, session: ClaudeProjectSession) -> None:
        _register_session_impl(
            self,
            work_dir,
            session,
            session_entry_cls=self._session_entry_cls,
            ensure_watchers_for_work_dir_fn=self._ensure_watchers_for_work_dir,
        )

    def _load_and_cache(self, work_dir: Path) -> Optional[_SessionEntry]:
        return _load_and_cache_impl(
            self,
            work_dir,
            session_entry_cls=self._session_entry_cls,
            load_session_fn=self._load_claude_session,
            find_session_file_fn=self._find_claude_session_file,
        )

    def invalidate(self, work_dir: Path) -> None:
        _invalidate_impl(
            self,
            work_dir,
            write_log_fn=write_registry_log,
            release_watchers_for_work_dir_fn=self._release_watchers_for_work_dir,
        )

    def remove(self, work_dir: Path) -> None:
        _remove_impl(
            self,
            work_dir,
            write_log_fn=write_registry_log,
            release_watchers_for_work_dir_fn=self._release_watchers_for_work_dir,
        )

    def _monitor_loop(self) -> None:
        _monitor_loop_impl(self)

    def _check_all_sessions(self) -> None:
        _check_all_sessions_impl(self, env_float_fn=_env_float, env_int_fn=_env_int)

    def _check_one(self, key: str, work_dir: Path, *, now: float, refresh_interval_s: float, scan_limit: int) -> None:
        _check_one_impl(
            self,
            key,
            work_dir,
            now=now,
            refresh_interval_s=refresh_interval_s,
            scan_limit=scan_limit,
            find_session_file_fn=self._find_claude_session_file,
            load_session_fn=self._load_claude_session,
            refresh_claude_log_binding_fn=_refresh_claude_log_binding,
            write_log_fn=write_registry_log,
        )

    def _load_claude_session(self, work_dir: Path) -> Optional[ClaudeProjectSession]:
        return load_claude_session(work_dir)

    def _project_dirs_for_work_dir(self, work_dir: Path, *, include_missing: bool = False) -> list[Path]:
        return _project_dirs_for_work_dir_impl(
            self,
            work_dir,
            candidate_project_dirs_fn=_candidate_project_dirs,
            include_missing=include_missing,
        )

    def _ensure_watchers_for_work_dir(self, work_dir: Path, key: str) -> None:
        _ensure_watchers_for_work_dir_impl(
            self,
            work_dir,
            key,
            has_watchdog=HAS_WATCHDOG,
            watcher_factory=SessionFileWatcher,
            candidate_project_dirs_fn=_candidate_project_dirs,
        )

    def _release_watchers_for_work_dir(self, work_dir: Path, key: str) -> None:
        _release_watchers_for_work_dir_impl(
            self,
            work_dir,
            key,
            has_watchdog=HAS_WATCHDOG,
            candidate_project_dirs_fn=_candidate_project_dirs,
        )

    def _stop_all_watchers(self) -> None:
        _stop_all_watchers_impl(self, has_watchdog=HAS_WATCHDOG)

    def _start_root_watcher(self) -> None:
        _start_root_watcher_impl(self, has_watchdog=HAS_WATCHDOG, watcher_factory=SessionFileWatcher)

    def _stop_root_watcher(self) -> None:
        _stop_root_watcher_impl(self)

    def _read_log_meta_with_retry(self, log_path: Path) -> tuple[Optional[str], Optional[str], Optional[bool]]:
        return read_log_meta_with_retry(log_path)

    def _find_claude_session_file(self, work_dir: Path) -> Optional[Path]:
        return find_claude_session_file(work_dir)

    def _update_session_file_direct(self, session_file: Path, log_path: Path, session_id: str) -> None:
        update_session_file_direct(session_file, log_path, session_id)

    def _on_new_log_file_global(self, path: Path) -> None:
        handle_new_log_file_global(self, path)

    def _on_new_log_file(self, project_key: str, path: Path) -> None:
        handle_new_log_file(self, project_key, path)

    def _on_sessions_index(self, project_key: str, index_path: Path) -> None:
        handle_sessions_index(self, project_key, index_path)

    def get_status(self) -> dict:
        with self._lock:
            return {
                "total": len(self._sessions),
                "valid": sum(1 for e in self._sessions.values() if e.valid),
                "sessions": [{"work_dir": str(e.work_dir), "valid": e.valid} for e in self._sessions.values()],
            }


__all__ = ["ClaudeSessionRegistry"]
