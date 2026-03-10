"""
CodeBuddy protocol helpers.

Wraps prompts with CCB markers and extracts replies — simplified version
without skills injection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ccb_protocol import (
    DONE_PREFIX,
    REQ_ID_PREFIX,
    is_done_text,
    make_req_id,
    strip_done_text,
)

ANY_DONE_LINE_RE = re.compile(r"^\s*CCB_DONE:\s*(?:[0-9a-f]{32}|\d{8}-\d{6}-\d{3}-\d+-\d+)\s*$", re.IGNORECASE)


def wrap_codebuddy_prompt(message: str, req_id: str) -> str:
    """Wrap a prompt with CCB protocol markers for CodeBuddy."""
    message = (message or "").rstrip()
    return (
        f"{REQ_ID_PREFIX} {req_id}\n\n"
        f"{message}\n\n"
        "IMPORTANT:\n"
        "- Reply with an execution summary, in English. Do not stay silent.\n"
        "- End your reply with this exact final line (verbatim, on its own line):\n"
        f"{DONE_PREFIX} {req_id}\n"
    )


def extract_reply_for_req(text: str, req_id: str) -> str:
    """
    Extract the reply segment for req_id from a CodeBuddy message.

    CodeBuddy may emit multiple replies in a single assistant message, each ending with its own
    `CCB_DONE: <req_id>` line. In that case, we want only the segment between the previous done line
    (any req_id) and the done line for our req_id.
    """
    lines = [ln.rstrip("\n") for ln in (text or "").splitlines()]
    if not lines:
        return ""

    target_re = re.compile(rf"^\s*CCB_DONE:\s*{re.escape(req_id)}\s*$", re.IGNORECASE)
    done_idxs = [i for i, ln in enumerate(lines) if ANY_DONE_LINE_RE.match(ln or "")]
    target_idxs = [i for i in done_idxs if target_re.match(lines[i] or "")]

    if not target_idxs:
        # No CCB_DONE for our req_id found
        # If there are other CCB_DONE markers, this is likely old content - return empty
        if done_idxs:
            return ""  # Prevent returning old content
        return strip_done_text(text, req_id)

    target_i = target_idxs[-1]
    prev_done_i = -1
    for i in reversed(done_idxs):
        if i < target_i:
            prev_done_i = i
            break

    segment = lines[prev_done_i + 1 : target_i]
    while segment and segment[0].strip() == "":
        segment = segment[1:]
    while segment and segment[-1].strip() == "":
        segment = segment[:-1]
    return "\n".join(segment).rstrip()


@dataclass(frozen=True)
class BaskdRequest:
    client_id: str
    work_dir: str
    timeout_s: float
    quiet: bool
    message: str
    output_path: str | None = None
    req_id: str | None = None
    caller: str = "claude"


@dataclass(frozen=True)
class BaskdResult:
    exit_code: int
    reply: str
    req_id: str
    session_key: str
    done_seen: bool
    done_ms: int | None = None
    anchor_seen: bool = False
    fallback_scan: bool = False
    anchor_ms: int | None = None
