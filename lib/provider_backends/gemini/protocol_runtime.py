from __future__ import annotations

import re

from provider_core.protocol import ANY_DONE_LINE_RE, DONE_PREFIX, REQ_ID_PREFIX, strip_done_text


def wrap_gemini_prompt(message: str, req_id: str) -> str:
    return "\n".join(prompt_sections(message, req_id=req_id)) + "\n"


def wrap_gemini_turn_prompt(message: str, req_id: str) -> str:
    rendered = (message or "").rstrip()
    return "\n".join(
        [
            f"{REQ_ID_PREFIX} {req_id}",
            "",
            rendered,
        ]
    ) + "\n"


def prompt_sections(message: str, *, req_id: str) -> list[str]:
    rendered = (message or "").rstrip()
    return [
        f"{REQ_ID_PREFIX} {req_id}",
        "",
        rendered,
        "",
        "IMPORTANT — you MUST follow these rules:",
        "1. Reply in English with an execution summary. Do not stay silent.",
        "2. Your FINAL line MUST be exactly (copy verbatim, no extra text):",
        f"   {DONE_PREFIX} {req_id}",
        "3. Do NOT omit, modify, or paraphrase the line above.",
    ]


def extract_reply_for_req(text: str, req_id: str) -> str:
    lines = [line.rstrip("\n") for line in (text or "").splitlines()]
    if not lines:
        return ""

    done_indexes = [index for index, line in enumerate(lines) if ANY_DONE_LINE_RE.match(line or "")]
    target_indexes = [index for index in done_indexes if done_target_re(req_id).match(lines[index] or "")]
    if not target_indexes:
        return "" if done_indexes else strip_done_text(text, req_id)

    segment = reply_segment(lines, done_indexes=done_indexes, target_index=target_indexes[-1])
    return "\n".join(segment).rstrip()


def done_target_re(req_id: str):
    return re.compile(rf"^\s*CCB_DONE:\s*{re.escape(req_id)}\s*$", re.IGNORECASE)


def reply_segment(lines: list[str], *, done_indexes: list[int], target_index: int) -> list[str]:
    start_index = previous_done_index(done_indexes, target_index=target_index) + 1
    return trim_blank_edges(lines[start_index:target_index])


def previous_done_index(done_indexes: list[int], *, target_index: int) -> int:
    for index in reversed(done_indexes):
        if index < target_index:
            return index
    return -1


def trim_blank_edges(lines: list[str]) -> list[str]:
    start = 0
    end = len(lines)
    while start < end and lines[start].strip() == "":
        start += 1
    while end > start and lines[end - 1].strip() == "":
        end -= 1
    return lines[start:end]


__all__ = ["extract_reply_for_req", "wrap_gemini_prompt", "wrap_gemini_turn_prompt"]
