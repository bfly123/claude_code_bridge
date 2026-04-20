from __future__ import annotations

from ..constants import ANY_DONE_LINE_RE, done_line_re, is_trailing_noise_line
from .utils import split_lines


def strip_trailing_markers(text: str) -> str:
    lines = split_lines(text)
    while lines:
        last = lines[-1]
        if is_trailing_noise_line(last) or ANY_DONE_LINE_RE.match(last or ''):
            lines.pop()
            continue
        break
    return '\n'.join(lines).rstrip()


def is_done_text(text: str, req_id: str) -> bool:
    lines = [line.rstrip() for line in (text or '').splitlines()]
    for index in range(len(lines) - 1, -1, -1):
        if is_trailing_noise_line(lines[index]):
            continue
        return bool(done_line_re(req_id).match(lines[index]))
    return False


def strip_done_text(text: str, req_id: str) -> str:
    lines = split_lines(text)
    if not lines:
        return ''
    while lines and is_trailing_noise_line(lines[-1]):
        lines.pop()
    if lines and done_line_re(req_id).match(lines[-1] or ''):
        lines.pop()
    while lines and is_trailing_noise_line(lines[-1]):
        lines.pop()
    return '\n'.join(lines).rstrip()


__all__ = ['is_done_text', 'strip_done_text', 'strip_trailing_markers']
