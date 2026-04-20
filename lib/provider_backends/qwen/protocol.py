"""
Qwen protocol helpers.

Wraps prompts with CCB markers and extracts replies — simplified version
without skills injection.
"""
from __future__ import annotations

from dataclasses import dataclass

from provider_core.protocol import (
    ANY_DONE_LINE_RE,
    DONE_PREFIX,
    REQ_ID_PREFIX,
    is_done_text,
    make_req_id,
    strip_done_text,
)

from .protocol_runtime import extract_reply_for_req, wrap_qwen_prompt


@dataclass(frozen=True)
class QwenRequest:
    client_id: str
    work_dir: str
    timeout_s: float
    quiet: bool
    message: str
    req_id: str | None = None
    caller: str = "claude"


@dataclass(frozen=True)
class QwenResult:
    exit_code: int
    reply: str
    req_id: str
    session_key: str
    done_seen: bool
    done_ms: int | None = None
    anchor_seen: bool = False
    fallback_scan: bool = False
    anchor_ms: int | None = None


__all__ = [
    "ANY_DONE_LINE_RE",
    "DONE_PREFIX",
    "QwenRequest",
    "QwenResult",
    "REQ_ID_PREFIX",
    "extract_reply_for_req",
    "is_done_text",
    "make_req_id",
    "strip_done_text",
    "wrap_qwen_prompt",
]
