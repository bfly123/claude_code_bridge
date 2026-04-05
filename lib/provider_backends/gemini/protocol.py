from __future__ import annotations

import re
from dataclasses import dataclass

from provider_core.protocol import (
    ANY_DONE_LINE_RE,
    DONE_PREFIX,
    REQ_ID_PREFIX,
    is_done_text,
    make_req_id,
    strip_done_text,
)


def wrap_gemini_prompt(message: str, req_id: str) -> str:
    message = (message or "").rstrip()
    return (
        f"{REQ_ID_PREFIX} {req_id}\n\n"
        f"{message}\n\n"
        "IMPORTANT — you MUST follow these rules:\n"
        "1. Reply in English with an execution summary. Do not stay silent.\n"
        "2. Your FINAL line MUST be exactly (copy verbatim, no extra text):\n"
        f"   {DONE_PREFIX} {req_id}\n"
        "3. Do NOT omit, modify, or paraphrase the line above.\n"
    )


def wrap_gemini_turn_prompt(message: str, req_id: str) -> str:
    message = (message or "").rstrip()
    return (
        f"{REQ_ID_PREFIX} {req_id}\n\n"
        f"{message}\n"
    )


def extract_reply_for_req(text: str, req_id: str) -> str:
    """
    Extract the reply segment for req_id from a Gemini message.

    Gemini sometimes emits multiple replies in a single assistant message, each ending with its own
    `CCB_DONE: <req_id>` line. In that case, we want only the segment between the previous done line
    (any req_id) and the done line for our req_id.
    """
    lines = [ln.rstrip("\n") for ln in (text or "").splitlines()]
    if not lines:
        return ""

    # Find last done-line index for this req_id (may not be last line if the model misbehaves).
    target_re = re.compile(rf"^\s*CCB_DONE:\s*{re.escape(req_id)}\s*$", re.IGNORECASE)
    done_idxs = [i for i, ln in enumerate(lines) if ANY_DONE_LINE_RE.match(ln or "")]
    target_idxs = [i for i in done_idxs if target_re.match(lines[i] or "")]

    if not target_idxs:
        # No CCB_DONE for our req_id found
        # If there are other CCB_DONE markers, this is likely old content - return empty
        if done_idxs:
            return ""  # Prevent returning old content
        # Fallback: keep existing behavior (strip only if the last line matches).
        return strip_done_text(text, req_id)

    target_i = target_idxs[-1]
    prev_done_i = -1
    for i in reversed(done_idxs):
        if i < target_i:
            prev_done_i = i
            break

    segment = lines[prev_done_i + 1 : target_i]
    # Trim leading/trailing blank lines for nicer output.
    while segment and segment[0].strip() == "":
        segment = segment[1:]
    while segment and segment[-1].strip() == "":
        segment = segment[:-1]
    return "\n".join(segment).rstrip()


@dataclass(frozen=True)
class GeminiRequest:
    client_id: str
    work_dir: str
    timeout_s: float
    quiet: bool
    message: str
    req_id: str | None = None
    caller: str = "claude"


@dataclass(frozen=True)
class GeminiResult:
    exit_code: int
    reply: str
    req_id: str
    session_key: str
    done_seen: bool
    done_ms: int | None = None
