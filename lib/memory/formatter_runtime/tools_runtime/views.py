from __future__ import annotations

from .input import format_tool_input


def format_tool_executions(executions: list, *, detailed: bool) -> list[str]:
    if detailed:
        return detailed_tool_executions(executions)
    return recent_tool_executions(executions)


def detailed_tool_executions(executions: list) -> list[str]:
    lines: list[str] = ['**All Tool Executions:**', '']
    for index, execution in enumerate(executions, 1):
        lines.append(f"#### {index}. {execution.name}" + (' ❌' if execution.is_error else ''))
        input_text = format_tool_input(execution.name, execution.input)
        if input_text:
            lines.append(f"- **Input**: `{input_text}`")
        if execution.result:
            lines.extend(['- **Result**:', '```', str(execution.result), '```'])
        lines.append('')
    return lines


def recent_tool_executions(executions: list) -> list[str]:
    lines: list[str] = ['**Recent Tool Executions:**', '']
    shown = 0
    for execution in executions[-10:]:
        if execution.name in {'Read', 'Glob', 'Grep'}:
            continue
        lines.append(f"- **{execution.name}**" + (' ❌' if execution.is_error else ''))
        input_text = format_tool_input(execution.name, execution.input)
        if input_text:
            lines.append(f'  - Input: {input_text}')
        if execution.result:
            lines.append(f"  - Result: `{result_preview(execution.result)}`")
        shown += 1
        if shown >= 5:
            break
    if len(executions) > 5:
        lines.append(f'- ... and {len(executions) - 5} more')
    lines.append('')
    return lines


def result_preview(result: object) -> str:
    preview = str(result)[:150].replace('\n', ' ')
    if len(str(result)) > 150:
        preview += '...'
    return preview


__all__ = ['detailed_tool_executions', 'format_tool_executions', 'recent_tool_executions', 'result_preview']
