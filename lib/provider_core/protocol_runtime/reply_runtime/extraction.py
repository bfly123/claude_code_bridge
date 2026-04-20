from __future__ import annotations

import re

from ..constants import ANY_DONE_LINE_RE
from .markers import strip_done_text
from .utils import previous_done_index, split_lines, trim_blank_edges


def extract_reply_for_req(text: str, req_id: str) -> str:
    lines = split_lines(text)
    if not lines:
        return ''
    done_indexes = done_line_indexes(lines)
    target_indexes = target_done_indexes(lines, req_id=req_id, done_indexes=done_indexes)
    if not target_indexes:
        return '' if done_indexes else strip_done_text(text, req_id)
    return extract_reply_window(lines, done_indexes=done_indexes, target_index=target_indexes[-1])


def done_target_re(req_id: str):
    return re.compile(rf'^\s*CCB_DONE:\s*{re.escape(req_id)}\s*$', re.IGNORECASE)


def done_line_indexes(lines: list[str]) -> list[int]:
    return [index for index, line in enumerate(lines) if ANY_DONE_LINE_RE.match(line or '')]


def target_done_indexes(lines: list[str], *, req_id: str, done_indexes: list[int] | None = None) -> list[int]:
    indexes = done_line_indexes(lines) if done_indexes is None else done_indexes
    target_re = done_target_re(req_id)
    return [index for index in indexes if target_re.match(lines[index] or '')]


def extract_reply_window(
    lines: list[str],
    *,
    done_indexes: list[int],
    target_index: int,
    start_index: int | None = None,
) -> str:
    if start_index is None:
        start = previous_done_index(done_indexes, target_index=target_index) + 1
    else:
        start = start_index
    segment = trim_blank_edges(lines[start:target_index])
    return '\n'.join(segment).rstrip()


__all__ = [
    'done_line_indexes',
    'done_target_re',
    'extract_reply_for_req',
    'extract_reply_window',
    'target_done_indexes',
]
