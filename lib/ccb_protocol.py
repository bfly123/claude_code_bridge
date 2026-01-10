from __future__ import annotations

import re
import secrets
from dataclasses import dataclass


REQ_ID_PREFIX = "CCB_REQ_ID:"
DONE_PREFIX = "CCB_DONE:"

DONE_LINE_RE_TEMPLATE = r"^\s*CCB_DONE:\s*{req_id}\s*$"


def make_req_id() -> str:
    # 128-bit token is enough; hex string is log/grep friendly.
    return secrets.token_hex(16)


def wrap_codex_prompt(message: str, req_id: str) -> str:
    message = (message or "").rstrip()
    return (
        f"{REQ_ID_PREFIX} {req_id}\n\n"
        f"{message}\n\n"
        "IMPORTANT:\n"
        "- Reply normally.\n"
        "- End your reply with this exact final line (verbatim, on its own line):\n"
        f"{DONE_PREFIX} {req_id}\n"
    )


def done_line_re(req_id: str) -> re.Pattern[str]:
    return re.compile(DONE_LINE_RE_TEMPLATE.format(req_id=re.escape(req_id)))


def is_done_text(text: str, req_id: str) -> bool:
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == "":
            continue
        return bool(done_line_re(req_id).match(lines[i]))
    return False


def strip_done_text(text: str, req_id: str) -> str:
    lines = [ln.rstrip("\n") for ln in (text or "").splitlines()]
    if not lines:
        return ""
    i = len(lines) - 1
    while i >= 0 and lines[i].strip() == "":
        i -= 1
    if i >= 0 and done_line_re(req_id).match(lines[i] or ""):
        lines = lines[:i]
    return "\n".join(lines).rstrip()


@dataclass(frozen=True)
class CaskdRequest:
    client_id: str
    work_dir: str
    timeout_s: float
    quiet: bool
    message: str
    output_path: str | None = None


@dataclass(frozen=True)
class CaskdResult:
    exit_code: int
    reply: str
    req_id: str
    session_key: str
    log_path: str | None
    anchor_seen: bool
    done_seen: bool
    fallback_scan: bool
    anchor_ms: int | None = None
    done_ms: int | None = None
