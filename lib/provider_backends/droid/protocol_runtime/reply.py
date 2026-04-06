from __future__ import annotations

import re

from provider_core.protocol import ANY_DONE_LINE_RE, strip_done_text


def extract_reply_for_req(text: str, req_id: str) -> str:
    lines = [line.rstrip("\n") for line in (text or "").splitlines()]
    if not lines:
        return ""

    done_indexes = _done_indexes(lines)
    target_indexes = _target_done_indexes(lines, req_id=req_id, done_indexes=done_indexes)
    if not target_indexes:
        return "" if done_indexes else strip_done_text(text, req_id)

    target_index = target_indexes[-1]
    previous_done_index = _previous_done_index(done_indexes, target_index=target_index)
    segment = _trim_blank_edges(lines[previous_done_index + 1 : target_index])
    return "\n".join(segment).rstrip()


def _done_indexes(lines: list[str]) -> list[int]:
    return [index for index, line in enumerate(lines) if ANY_DONE_LINE_RE.match(line or "")]


def _target_done_indexes(lines: list[str], *, req_id: str, done_indexes: list[int]) -> list[int]:
    target_re = re.compile(rf"^\s*CCB_DONE:\s*{re.escape(req_id)}\s*$", re.IGNORECASE)
    return [index for index in done_indexes if target_re.match(lines[index] or "")]


def _previous_done_index(done_indexes: list[int], *, target_index: int) -> int:
    for index in reversed(done_indexes):
        if index < target_index:
            return index
    return -1


def _trim_blank_edges(lines: list[str]) -> list[str]:
    start = 0
    end = len(lines)
    while start < end and lines[start].strip() == "":
        start += 1
    while end > start and lines[end - 1].strip() == "":
        end -= 1
    return lines[start:end]


__all__ = ["extract_reply_for_req"]
