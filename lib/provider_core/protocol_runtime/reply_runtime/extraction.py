from __future__ import annotations

import re

from ..constants import ANY_DONE_LINE_RE
from .markers import strip_done_text
from .utils import previous_done_index, split_lines, trim_blank_edges


def extract_reply_for_req(text: str, req_id: str) -> str:
    lines = split_lines(text)
    if not lines:
        return ''
    target_re = re.compile(rf'^\s*CCB_DONE:\s*{re.escape(req_id)}\s*$', re.IGNORECASE)
    done_indexes = [index for index, line in enumerate(lines) if ANY_DONE_LINE_RE.match(line or '')]
    target_indexes = [index for index in done_indexes if target_re.match(lines[index] or '')]
    if not target_indexes:
        return '' if done_indexes else strip_done_text(text, req_id)
    target_index = target_indexes[-1]
    segment = trim_blank_edges(lines[previous_done_index(done_indexes, target_index=target_index) + 1 : target_index])
    return '\n'.join(segment).rstrip()


__all__ = ['extract_reply_for_req']
