from __future__ import annotations


def format_tool_input(name: str, inp: dict) -> str:
    if not inp:
        return ''
    if name in {'Write', 'Edit'}:
        return inp.get('file_path', '')
    if name == 'Bash':
        cmd = inp.get('command', '')
        return cmd[:80] + '...' if len(cmd) > 80 else cmd
    if name == 'TaskCreate':
        return inp.get('subject', '')
    if name == 'TaskUpdate':
        return f"#{inp.get('taskId', '')} -> {inp.get('status', '')}"
    return ''


__all__ = ['format_tool_input']
