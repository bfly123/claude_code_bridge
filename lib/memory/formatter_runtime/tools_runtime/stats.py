from __future__ import annotations

from typing import Optional

from memory.types import SessionStats

from .views import format_tool_executions


def format_stats_section(stats: Optional[SessionStats], *, detailed: bool = False) -> list[str]:
    if not stats:
        return []
    lines = ['### Session Activity Summary', '']
    lines.extend(tool_calls_section(stats))
    lines.extend(path_section('**Files Created/Written:**', stats.files_written, limit=(50 if detailed else 15)))
    lines.extend(path_section('**Files Edited:**', stats.files_edited, limit=(30 if detailed else 10), truncate_notice=False))
    lines.extend(path_section('**Files Read:**', stats.files_read, limit=(30 if detailed else 10)))
    if stats.tasks_created > 0:
        lines.extend([f'**Tasks:** {stats.tasks_completed}/{stats.tasks_created} completed', ''])
    if stats.tool_executions:
        lines.extend(format_tool_executions(stats.tool_executions, detailed=detailed))
    lines.extend(['---', ''])
    return lines


def tool_calls_section(stats: SessionStats) -> list[str]:
    if not stats.tool_calls:
        return []
    lines = ['**Tool Calls:**']
    for name, count in sorted(stats.tool_calls.items(), key=lambda item: -item[1]):
        lines.append(f'- {name}: {count}')
    lines.append('')
    return lines


def path_section(title: str, paths: list[str], *, limit: int, truncate_notice: bool = True) -> list[str]:
    if not paths:
        return []
    lines = [title]
    for path in paths[:limit]:
        lines.append(f'- `{path}`')
    if truncate_notice and len(paths) > limit:
        lines.append(f'- ... and {len(paths) - limit} more')
    lines.append('')
    return lines


__all__ = ['format_stats_section', 'path_section', 'tool_calls_section']
