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
    blocks: List[str] = []
    req_positions = [(match.end(), match.group(1)) for match in _CCB_REQ_ID_RE.finditer(text)]
    done_positions = [match.start() for match in _CCB_DONE_RE.finditer(text)]

    if not req_positions and not done_positions:
        stripped = text.strip()
        if stripped:
            blocks.append(stripped)
        return blocks

    for req_end, _req_id in req_positions:
        next_done = None
        for done_pos in done_positions:
            if done_pos > req_end:
                next_done = done_pos
                break
        if next_done is not None:
            segment = text[req_end:next_done].strip()
            if segment:
                blocks.append(segment)
        else:
            segment = text[req_end:].strip()
            if segment:
                blocks.append(segment)

    return blocks


def extract_conversation_pairs(text: str) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    req_matches = list(_CCB_REQ_ID_RE.finditer(text))
    done_positions = [match.start() for match in _CCB_DONE_RE.finditer(text)]

    prev_end = 0
    for req_match in req_matches:
        user_text = text[prev_end:req_match.start()].strip()
        req_end = req_match.end()

        next_done = None
        for done_pos in done_positions:
            if done_pos > req_end:
                next_done = done_pos
                break

        if next_done is not None:
            assistant_text = text[req_end:next_done].strip()
            prev_end = next_done
        else:
            assistant_text = text[req_end:].strip()
            prev_end = len(text)

        pairs.append((user_text, assistant_text))

    return pairs


__all__ = ['extract_assistant_blocks', 'extract_conversation_pairs', 'strip_ansi']
