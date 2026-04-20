from __future__ import annotations

from pathlib import Path
from typing import Optional

from provider_backends.claude.registry_support.pathing import (
    candidate_project_dirs as _candidate_project_dirs,
)
from provider_sessions.watch import HAS_WATCHDOG, SessionFileWatcher

from . import (
    ensure_watchers_for_work_dir as _ensure_watchers_for_work_dir_impl,
    handle_new_log_file,
    handle_new_log_file_global,
    handle_sessions_index,
    project_dirs_for_work_dir as _project_dirs_for_work_dir_impl,
    read_log_meta_with_retry,
    release_watchers_for_work_dir as _release_watchers_for_work_dir_impl,
    start_root_watcher as _start_root_watcher_impl,
    stop_all_watchers as _stop_all_watchers_impl,
    stop_root_watcher as _stop_root_watcher_impl,
    update_session_file_direct,
)


class ClaudeRegistryWatcherMixin:
    def _project_dirs_for_work_dir(
        self,
        work_dir: Path,
        *,
        include_missing: bool = False,
    ) -> list[Path]:
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
        _start_root_watcher_impl(
            self,
            has_watchdog=HAS_WATCHDOG,
            watcher_factory=SessionFileWatcher,
        )

    def _stop_root_watcher(self) -> None:
        _stop_root_watcher_impl(self)

    def _read_log_meta_with_retry(
        self,
        log_path: Path,
    ) -> tuple[Optional[str], Optional[str], Optional[bool]]:
        return read_log_meta_with_retry(log_path)

    def _update_session_file_direct(
        self,
        session_file: Path,
        log_path: Path,
        session_id: str,
    ) -> None:
        update_session_file_direct(session_file, log_path, session_id)

    def _on_new_log_file_global(self, path: Path) -> None:
        handle_new_log_file_global(self, path)

    def _on_new_log_file(self, project_key: str, path: Path) -> None:
        handle_new_log_file(self, project_key, path)

    def _on_sessions_index(self, project_key: str, index_path: Path) -> None:
        handle_sessions_index(self, project_key, index_path)


__all__ = ['ClaudeRegistryWatcherMixin']
