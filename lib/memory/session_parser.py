"""
Parse Claude JSONL session files and extract conversations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .types import ConversationEntry, SessionInfo, SessionStats, ToolExecution, SessionNotFoundError, SessionParseError
from .session_parser_runtime import (
    CLAUDE_PROJECTS_ROOT,
    build_tool_executions,
    collect_stats,
    extract_content,
    extract_file_info,
    extract_session_stats,
    extract_tool_calls,
    find_session_file,
    get_project_dir,
    parse_entry,
    parse_session,
    resolve_from_index,
    resolve_session,
    scan_all_projects,
    scan_project_dir,
)


class ClaudeSessionParser:
    """Parse Claude JSONL session files."""

    def __init__(self, root: Optional[Path] = None):
        self.root = root or CLAUDE_PROJECTS_ROOT

    def resolve_session(self, work_dir: Path, session_path: Optional[Path] = None) -> Path:
        return resolve_session(self, work_dir, session_path=session_path)

    def _resolve_from_index(self, work_dir: Path) -> Optional[Path]:
        return resolve_from_index(self, work_dir)

    def _find_session_file(self, session_id: str, work_dir: Path) -> Optional[Path]:
        return find_session_file(self, session_id, work_dir)

    def _get_project_dir(self, work_dir: Path) -> Optional[Path]:
        return get_project_dir(self, work_dir)

    def _scan_project_dir(self, work_dir: Path) -> Optional[Path]:
        return scan_project_dir(self, work_dir)

    def _scan_all_projects(self) -> Optional[Path]:
        return scan_all_projects(self)

    def parse_session(self, session_path: Path) -> list[ConversationEntry]:
        return parse_session(self, session_path)

    def _parse_entry(self, obj: dict) -> Optional[ConversationEntry]:
        return parse_entry(self, obj)

    def _extract_content(self, message: dict) -> str:
        return extract_content(self, message)

    def _extract_tool_calls(self, message: dict) -> list[dict]:
        return extract_tool_calls(self, message)

    def get_session_info(self, session_path: Path) -> SessionInfo:
        """Get information about a session."""
        return SessionInfo(
            session_id=session_path.stem,
            session_path=str(session_path),
            last_modified=session_path.stat().st_mtime if session_path.exists() else None,
        )

    def extract_session_stats(self, session_path: Path) -> SessionStats:
        return extract_session_stats(self, session_path)

    def _collect_stats(
        self,
        obj: dict,
        stats: SessionStats,
        seen_files: set[str],
        tool_uses: dict[str, dict],
        tool_results: dict[str, dict],
    ) -> None:
        collect_stats(self, obj, stats, seen_files, tool_uses, tool_results)

    def _extract_file_info(
        self, tool_name: str, inp: dict, stats: SessionStats, seen_files: set[str]
    ) -> None:
        extract_file_info(tool_name, inp, stats, seen_files)

    def _build_tool_executions(
        self,
        stats: SessionStats,
        tool_uses: dict[str, dict],
        tool_results: dict[str, dict],
    ) -> None:
        build_tool_executions(self, stats, tool_uses, tool_results)
