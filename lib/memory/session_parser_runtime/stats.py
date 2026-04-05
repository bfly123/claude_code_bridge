from __future__ import annotations

import json
from pathlib import Path

from memory.types import SessionNotFoundError, SessionParseError, SessionStats, ToolExecution


def extract_session_stats(parser, session_path: Path) -> SessionStats:
    if not session_path.exists():
        raise SessionNotFoundError(f"Session file not found: {session_path}")

    stats = SessionStats()
    seen_files: set[str] = set()
    tool_uses: dict[str, dict] = {}
    tool_results: dict[str, dict] = {}

    try:
        content = session_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise SessionParseError(f"Failed to read session file: {exc}")

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            collect_stats(parser, obj, stats, seen_files, tool_uses, tool_results)
        except json.JSONDecodeError:
            continue

    build_tool_executions(parser, stats, tool_uses, tool_results)
    return stats


def collect_stats(
    parser,
    obj: dict,
    stats: SessionStats,
    seen_files: set[str],
    tool_uses: dict[str, dict],
    tool_results: dict[str, dict],
) -> None:
    del parser
    if not isinstance(obj, dict):
        return

    msg_type = obj.get("type")
    message = obj.get("message", {})
    content = message.get("content", [])
    if not isinstance(content, list):
        content = []

    if msg_type == "assistant":
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tool_id = block.get("id", "")
                name = block.get("name", "unknown")
                tool_input = block.get("input", {})
                stats.tool_calls[name] = stats.tool_calls.get(name, 0) + 1
                tool_uses[tool_id] = {"name": name, "input": tool_input}
                extract_file_info(name, tool_input, stats, seen_files)

    if msg_type == "user":
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_result":
                tool_id = block.get("tool_use_id", "")
                result_content = block.get("content", "")
                if isinstance(result_content, str) and len(result_content) > 2000:
                    result_content = result_content[:2000] + "...[truncated]"
                tool_results[tool_id] = {
                    "content": result_content,
                    "is_error": block.get("is_error", False),
                }

    if msg_type == "file-history-snapshot":
        snapshot = obj.get("snapshot", {})
        backups = snapshot.get("trackedFileBackups", {})
        for path in backups.keys():
            if path not in seen_files:
                stats.files_written.append(path)
                seen_files.add(path)


def extract_file_info(tool_name: str, tool_input: dict, stats: SessionStats, seen_files: set[str]) -> None:
    if not isinstance(tool_input, dict):
        return

    file_path = tool_input.get("file_path") or tool_input.get("path")
    if tool_name == "Write":
        if file_path and file_path not in seen_files:
            stats.files_written.append(file_path)
            seen_files.add(file_path)
    elif tool_name == "Read":
        if file_path and file_path not in seen_files:
            stats.files_read.append(file_path)
            seen_files.add(file_path)
    elif tool_name == "Edit":
        if file_path and file_path not in seen_files:
            stats.files_edited.append(file_path)
            seen_files.add(file_path)
    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if cmd and len(stats.bash_commands) < 20:
            if len(cmd) > 100:
                cmd = cmd[:100] + "..."
            stats.bash_commands.append(cmd)
    elif tool_name == "TaskCreate":
        stats.tasks_created += 1
    elif tool_name == "TaskUpdate":
        status = tool_input.get("status", "")
        if status == "completed":
            stats.tasks_completed += 1


def build_tool_executions(parser, stats: SessionStats, tool_uses: dict[str, dict], tool_results: dict[str, dict]) -> None:
    del parser
    for tool_id, tool_use in tool_uses.items():
        result = tool_results.get(tool_id, {})
        stats.tool_executions.append(
            ToolExecution(
                tool_id=tool_id,
                name=tool_use.get("name", "unknown"),
                input=tool_use.get("input", {}),
                result=result.get("content"),
                is_error=result.get("is_error", False),
            )
        )


__all__ = [
    "build_tool_executions",
    "collect_stats",
    "extract_file_info",
    "extract_session_stats",
]
