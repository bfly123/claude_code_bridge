from __future__ import annotations

from pathlib import Path
from typing import Any

from . import (
    capture_state as _capture_reader_state,
    format_subagent_text as _format_subagent_text_impl,
    initialize_reader as _initialize_reader,
    latest_conversations as _latest_conversations_impl,
    latest_message as _latest_message_impl,
    latest_session as _latest_session_impl,
    list_subagent_logs as _list_subagent_logs_impl,
    parse_sessions_index as _parse_sessions_index_impl,
    project_dir as _project_dir_impl,
    read_new_entries as _read_new_entries_impl,
    read_new_events as _read_new_events_impl,
    read_new_events_for_file as _read_new_events_for_file_impl,
    read_new_messages as _read_new_messages_impl,
    read_new_subagent_events as _read_new_subagent_events_impl,
    read_since as _read_since_impl,
    read_since_entries as _read_since_entries_impl,
    read_since_events as _read_since_events_impl,
    scan_latest_session as _scan_latest_session_impl,
    scan_latest_session_any_project as _scan_latest_session_any_project_impl,
    session_belongs_to_current_project as _session_belongs_to_current_project_impl,
    session_is_sidechain as _session_is_sidechain_impl,
    set_preferred_session as _set_preferred_session_impl,
    subagent_state_for_session as _subagent_state_for_session_impl,
)
from .paths import CLAUDE_PROJECTS_ROOT


class ClaudeLogReader:
    """Reads Claude session logs from ~/.claude/projects/<key>."""

    def __init__(
        self,
        root: Path | None = None,
        work_dir: Path | None = None,
        *,
        use_sessions_index: bool = True,
        include_subagents: bool = False,
        include_subagent_user: bool = False,
        subagent_tag: str = "[subagent]",
    ):
        _initialize_reader(
            self,
            root=CLAUDE_PROJECTS_ROOT if root is None else root,
            work_dir=work_dir,
            use_sessions_index=use_sessions_index,
            include_subagents=include_subagents,
            include_subagent_user=include_subagent_user,
            subagent_tag=subagent_tag,
        )

    def _session_belongs_to_current_project(self, session_path: Path) -> bool:
        return _session_belongs_to_current_project_impl(self, session_path)

    def _project_dir(self) -> Path:
        return _project_dir_impl(self)

    def _session_is_sidechain(self, session_path: Path) -> bool | None:
        return _session_is_sidechain_impl(session_path)

    def _parse_sessions_index(self) -> Path | None:
        return _parse_sessions_index_impl(self)

    def _scan_latest_session_any_project(self) -> Path | None:
        return _scan_latest_session_any_project_impl(self)

    def _scan_latest_session(self) -> Path | None:
        return _scan_latest_session_impl(self)

    def _latest_session(self) -> Path | None:
        return _latest_session_impl(self)

    def set_preferred_session(self, session_path: Path | None) -> None:
        _set_preferred_session_impl(self, session_path)

    def current_session_path(self) -> Path | None:
        return self._latest_session()

    def capture_state(self) -> dict[str, Any]:
        return _capture_reader_state(self)

    def wait_for_message(self, state: dict[str, Any], timeout: float) -> tuple[str | None, dict[str, Any]]:
        return self._read_since(state, timeout=timeout, block=True)

    def try_get_message(self, state: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
        return self._read_since(state, timeout=0.0, block=False)

    def wait_for_events(self, state: dict[str, Any], timeout: float) -> tuple[list[tuple[str, str]], dict[str, Any]]:
        return self._read_since_events(state, timeout=timeout, block=True)

    def try_get_events(self, state: dict[str, Any]) -> tuple[list[tuple[str, str]], dict[str, Any]]:
        return self._read_since_events(state, timeout=0.0, block=False)

    def wait_for_entries(self, state: dict[str, Any], timeout: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return self._read_since_entries(state, timeout=timeout, block=True)

    def try_get_entries(self, state: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return self._read_since_entries(state, timeout=0.0, block=False)

    def latest_message(self) -> str | None:
        return _latest_message_impl(self)

    def latest_conversations(self, n: int) -> list[tuple[str, str]]:
        return _latest_conversations_impl(self, n)

    def _read_since(self, state: dict[str, Any], timeout: float, block: bool) -> tuple[str | None, dict[str, Any]]:
        return _read_since_impl(self, state, timeout, block)

    def _read_new_messages(self, session: Path, state: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
        return _read_new_messages_impl(self, session, state)

    def _read_since_events(
        self, state: dict[str, Any], timeout: float, block: bool
    ) -> tuple[list[tuple[str, str]], dict[str, Any]]:
        return _read_since_events_impl(self, state, timeout, block)

    def _read_since_entries(
        self, state: dict[str, Any], timeout: float, block: bool
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return _read_since_entries_impl(self, state, timeout, block)

    def _read_new_events(self, session: Path, state: dict[str, Any]) -> tuple[list[tuple[str, str]], dict[str, Any]]:
        return _read_new_events_impl(self, session, state)

    def _read_new_entries(self, session: Path, state: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return _read_new_entries_impl(self, session, state)

    def _subagent_state_for_session(self, session: Path, *, start_from_end: bool) -> dict[str, dict[str, Any]]:
        return _subagent_state_for_session_impl(self, session, start_from_end=start_from_end)

    def _list_subagent_logs(self, session: Path) -> list[Path]:
        return _list_subagent_logs_impl(self, session)

    def _format_subagent_text(self, text: str, entry: dict) -> str:
        return _format_subagent_text_impl(self, text, entry)

    def _read_new_subagent_events(
        self, session: Path, state: dict[str, Any]
    ) -> tuple[list[tuple[str, str]], dict[str, Any]]:
        return _read_new_subagent_events_impl(self, session, state)

    def _read_new_events_for_file(
        self, path: Path, offset: int, carry: bytes
    ) -> tuple[list[tuple[str, str, dict]], dict[str, Any]]:
        return _read_new_events_for_file_impl(self, path, offset, carry)


__all__ = ["ClaudeLogReader"]
