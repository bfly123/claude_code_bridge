from __future__ import annotations

from pathlib import Path
from typing import Optional

from provider_backends.claude.session import ClaudeProjectSession

from . import (
    get_session as _get_session_impl,
    invalidate as _invalidate_impl,
    load_and_cache as _load_and_cache_impl,
    register_session as _register_session_impl,
    remove as _remove_impl,
)
from .binding_runtime import find_claude_session_file, load_claude_session
from .logging import write_registry_log


class ClaudeRegistrySessionMixin:
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

    def _load_and_cache(self, work_dir: Path):
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

    def _load_claude_session(self, work_dir: Path) -> Optional[ClaudeProjectSession]:
        return load_claude_session(work_dir)

    def _find_claude_session_file(self, work_dir: Path) -> Optional[Path]:
        return find_claude_session_file(work_dir)


__all__ = ['ClaudeRegistrySessionMixin']
