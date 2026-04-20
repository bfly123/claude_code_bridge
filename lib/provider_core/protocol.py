from __future__ import annotations

from dataclasses import dataclass
from re import Pattern

from .protocol_runtime import (
    ANY_DONE_LINE_RE,
    ANY_REQ_ID_PATTERN,
    BEGIN_PREFIX,
    DONE_PREFIX,
    REQ_ID_BOUNDARY_PATTERN,
    REQ_ID_PREFIX,
    done_line_re,
    extract_reply_for_req,
    is_done_text,
    make_req_id,
    request_anchor_for_job,
    strip_done_text,
    strip_trailing_markers,
    wrap_codex_prompt,
    wrap_codex_turn_prompt,
)


@dataclass(frozen=True)
class CodexRequest:
    client_id: str
    work_dir: str
    timeout_s: float
    quiet: bool
    message: str
    req_id: str | None = None
    caller: str = 'claude'


@dataclass(frozen=True)
class CodexResult:
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


__all__ = [
    'ANY_DONE_LINE_RE',
    'ANY_REQ_ID_PATTERN',
    'BEGIN_PREFIX',
    'CodexRequest',
    'CodexResult',
    'DONE_PREFIX',
    'REQ_ID_BOUNDARY_PATTERN',
    'REQ_ID_PREFIX',
    'Pattern',
    'done_line_re',
    'extract_reply_for_req',
    'is_done_text',
    'make_req_id',
    'request_anchor_for_job',
    'strip_done_text',
    'strip_trailing_markers',
    'wrap_codex_prompt',
    'wrap_codex_turn_prompt',
]
