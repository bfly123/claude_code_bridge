from __future__ import annotations

import re

from provider_core.protocol import ANY_DONE_LINE_RE, BEGIN_PREFIX, strip_done_text


def extract_reply_for_req(text: str, req_id: str) -> str:
    lines = [ln.rstrip('\n') for ln in (text or '').splitlines()]
    if not lines:
        return ''
    target_re = re.compile(rf'^\s*CCB_DONE:\s*{re.escape(req_id)}\s*$', re.IGNORECASE)
    begin_re = re.compile(rf'^\s*{re.escape(BEGIN_PREFIX)}\s*{re.escape(req_id)}\s*$', re.IGNORECASE)
    done_idxs = [i for i, ln in enumerate(lines) if ANY_DONE_LINE_RE.match(ln or '')]
    target_idxs = [i for i in done_idxs if target_re.match(lines[i] or '')]
    if not target_idxs:
        return strip_done_text(text, req_id)
    target_i = target_idxs[-1]
    begin_i = _last_begin_index(lines, begin_re=begin_re, target_i=target_i)
    if begin_i is not None:
        segment = lines[begin_i + 1 : target_i]
    else:
        segment = lines[_previous_done_index(done_idxs, target_i=target_i) + 1 : target_i]
    return _trim_segment(segment)


def _last_begin_index(lines: list[str], *, begin_re, target_i: int) -> int | None:
    for i in range(target_i - 1, -1, -1):
        if begin_re.match(lines[i] or ''):
            return i
    return None


def _previous_done_index(done_idxs: list[int], *, target_i: int) -> int:
    for i in reversed(done_idxs):
        if i < target_i:
            return i
    return -1


def _trim_segment(segment: list[str]) -> str:
    while segment and segment[0].strip() == '':
        segment = segment[1:]
    while segment and segment[-1].strip() == '':
        segment = segment[:-1]
    return '\n'.join(segment).rstrip()


__all__ = ['extract_reply_for_req']
