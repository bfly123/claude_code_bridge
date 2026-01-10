from __future__ import annotations

from dataclasses import dataclass

from ccb_protocol import (
    DONE_PREFIX,
    REQ_ID_PREFIX,
    is_done_text,
    make_req_id,
    strip_done_text,
)


def wrap_opencode_prompt(message: str, req_id: str) -> str:
    message = (message or "").rstrip()
    return (
        f"{REQ_ID_PREFIX} {req_id}\n\n"
        f"{message}\n\n"
        "IMPORTANT:\n"
        "- Reply normally.\n"
        "- End your reply with this exact final line (verbatim, on its own line):\n"
        f"{DONE_PREFIX} {req_id}\n"
    )


@dataclass(frozen=True)
class OaskdRequest:
    client_id: str
    work_dir: str
    timeout_s: float
    quiet: bool
    message: str
    output_path: str | None = None


@dataclass(frozen=True)
class OaskdResult:
    exit_code: int
    reply: str
    req_id: str
    session_key: str
    done_seen: bool
    done_ms: int | None = None
