from __future__ import annotations

import re
from typing import List, Tuple

from provider_core.protocol import ANY_REQ_ID_PATTERN

_ANSI_ESCAPE_RE = re.compile(
    r"""
    \x1b
    (?:
      \[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]
    | \].*?(?:\x07|\x1b\\)
    | [\x40-\x5f]
    )
    """,
    re.VERBOSE,
)
_CCB_REQ_ID_RE = re.compile(r"^\s*CCB_REQ_ID:\s*(\S+)\s*$", re.MULTILINE)
_CCB_DONE_RE = re.compile(
    rf"^\s*CCB_DONE:\s*{ANY_REQ_ID_PATTERN}\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text)


def extract_assistant_blocks(text: str) -> List[str]:
    if not _has_protocol_markers(text):
        stripped = text.strip()
        return [stripped] if stripped else []

    return [assistant for _user, assistant in _conversation_segments(text) if assistant]


def extract_conversation_pairs(text: str) -> List[Tuple[str, str]]:
    return list(_conversation_segments(text))


def _has_protocol_markers(text: str) -> bool:
    return bool(_CCB_REQ_ID_RE.search(text) or _CCB_DONE_RE.search(text))


def _conversation_segments(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    done_positions = [match.start() for match in _CCB_DONE_RE.finditer(text)]
    prev_end = 0
    for req_match in _CCB_REQ_ID_RE.finditer(text):
        user_text = text[prev_end:req_match.start()].strip()
        assistant_text, prev_end = _assistant_segment(text, req_match.end(), done_positions)
        pairs.append((user_text, assistant_text))
    return pairs


def _assistant_segment(
    text: str,
    req_end: int,
    done_positions: list[int],
) -> tuple[str, int]:
    next_done = _next_done_position(done_positions, req_end)
    if next_done is None:
        return text[req_end:].strip(), len(text)
    return text[req_end:next_done].strip(), next_done


def _next_done_position(done_positions: list[int], req_end: int) -> int | None:
    for done_pos in done_positions:
        if done_pos > req_end:
            return done_pos
    return None


__all__ = ['extract_assistant_blocks', 'extract_conversation_pairs', 'strip_ansi']
