from __future__ import annotations

from memory.types import SessionStats, ToolExecution


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
    msg_type = obj.get('type')
    message = obj.get('message', {})
    content = message.get('content', [])
    if not isinstance(content, list):
        content = []
    if msg_type == 'assistant':
        _collect_assistant_blocks(content, stats, seen_files, tool_uses)
    if msg_type == 'user':
        _collect_tool_results(content, tool_results)
    if msg_type == 'file-history-snapshot':
        _collect_file_snapshot(obj.get('snapshot', {}), stats, seen_files)


def extract_file_info(tool_name: str, tool_input: dict, stats: SessionStats, seen_files: set[str]) -> None:
    if not isinstance(tool_input, dict):
        return
    file_path = tool_input.get('file_path') or tool_input.get('path')
    if tool_name == 'Write':
        _record_unique_path(file_path, stats.files_written, seen_files)
        return
    if tool_name == 'Read':
        _record_unique_path(file_path, stats.files_read, seen_files)
        return
    if tool_name == 'Edit':
        _record_unique_path(file_path, stats.files_edited, seen_files)
        return
    if tool_name == 'Bash':
        _record_bash_command(tool_input.get('command', ''), stats)
        return
    if tool_name == 'TaskCreate':
        stats.tasks_created += 1
        return
    if tool_name == 'TaskUpdate' and tool_input.get('status', '') == 'completed':
        stats.tasks_completed += 1


def build_tool_executions(parser, stats: SessionStats, tool_uses: dict[str, dict], tool_results: dict[str, dict]) -> None:
    del parser
    for tool_id, tool_use in tool_uses.items():
        result = tool_results.get(tool_id, {})
        stats.tool_executions.append(
            ToolExecution(
                tool_id=tool_id,
                name=tool_use.get('name', 'unknown'),
                input=tool_use.get('input', {}),
                result=result.get('content'),
                is_error=result.get('is_error', False),
            )
        )


def _collect_assistant_blocks(content: list, stats: SessionStats, seen_files: set[str], tool_uses: dict[str, dict]) -> None:
    for block in content:
        if not isinstance(block, dict) or block.get('type') != 'tool_use':
            continue
        tool_id = block.get('id', '')
        name = block.get('name', 'unknown')
        tool_input = block.get('input', {})
        stats.tool_calls[name] = stats.tool_calls.get(name, 0) + 1
        tool_uses[tool_id] = {'name': name, 'input': tool_input}
        extract_file_info(name, tool_input, stats, seen_files)


def _collect_tool_results(content: list, tool_results: dict[str, dict]) -> None:
    for block in content:
        if not isinstance(block, dict) or block.get('type') != 'tool_result':
            continue
        tool_id = block.get('tool_use_id', '')
        result_content = block.get('content', '')
        if isinstance(result_content, str) and len(result_content) > 2000:
            result_content = result_content[:2000] + '...[truncated]'
        tool_results[tool_id] = {
            'content': result_content,
            'is_error': block.get('is_error', False),
        }


def _collect_file_snapshot(snapshot: dict, stats: SessionStats, seen_files: set[str]) -> None:
    backups = snapshot.get('trackedFileBackups', {})
    for path in backups.keys():
        _record_unique_path(path, stats.files_written, seen_files)


def _record_unique_path(path: object, target: list[str], seen_files: set[str]) -> None:
    text = str(path or '').strip()
    if not text or text in seen_files:
        return
    target.append(text)
    seen_files.add(text)


def _record_bash_command(command: object, stats: SessionStats) -> None:
    cmd = str(command or '').strip()
    if not cmd or len(stats.bash_commands) >= 20:
        return
    if len(cmd) > 100:
        cmd = cmd[:100] + '...'
    stats.bash_commands.append(cmd)


__all__ = ['build_tool_executions', 'collect_stats', 'extract_file_info']
