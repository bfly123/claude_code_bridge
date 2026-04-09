from __future__ import annotations

import re

from provider_core.protocol import BEGIN_PREFIX, strip_done_text
from provider_core.protocol_runtime.reply_runtime.extraction import (
    done_line_indexes,
    extract_reply_window,
    target_done_indexes,
)
from provider_core.protocol_runtime.reply_runtime.utils import split_lines


def extract_reply_for_req(text: str, req_id: str) -> str:
    lines = split_lines(text)
    if not lines:
        return ''
    begin_re = re.compile(rf'^\s*{re.escape(BEGIN_PREFIX)}\s*{re.escape(req_id)}\s*$', re.IGNORECASE)
    done_indexes = done_line_indexes(lines)
    target_indexes = target_done_indexes(lines, req_id=req_id, done_indexes=done_indexes)
    if not target_indexes:
        return strip_done_text(text, req_id)
    target_index = target_indexes[-1]
    begin_index = _last_begin_index(lines, begin_re=begin_re, target_index=target_index)
    start_index = None if begin_index is None else begin_index + 1
    return extract_reply_window(
        lines,
        done_indexes=done_indexes,
        target_index=target_index,
        start_index=start_index,
    )


def _last_begin_index(lines: list[str], *, begin_re, target_index: int) -> int | None:
    for index in range(target_index - 1, -1, -1):
        if begin_re.match(lines[index] or ''):
            return index
    return None


__all__ = ['extract_reply_for_req']
