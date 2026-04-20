from __future__ import annotations

import json
from pathlib import Path

from memory.types import SessionNotFoundError, SessionParseError, SessionStats

from .collection import build_tool_executions, collect_stats


def extract_session_stats(parser, session_path: Path) -> SessionStats:
    if not session_path.exists():
        raise SessionNotFoundError(f'Session file not found: {session_path}')
    stats = SessionStats()
    seen_files: set[str] = set()
    tool_uses: dict[str, dict] = {}
    tool_results: dict[str, dict] = {}
    for obj in iter_session_objects(session_path):
        collect_stats(parser, obj, stats, seen_files, tool_uses, tool_results)
    build_tool_executions(parser, stats, tool_uses, tool_results)
    return stats


def iter_session_objects(session_path: Path):
    try:
        content = session_path.read_text(encoding='utf-8', errors='replace')
    except Exception as exc:
        raise SessionParseError(f'Failed to read session file: {exc}')
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


__all__ = ['extract_session_stats', 'iter_session_objects']
