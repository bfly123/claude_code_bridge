from __future__ import annotations

from dataclasses import dataclass

from provider_core.protocol import (
    REQ_ID_PREFIX,
    make_req_id,
)


def wrap_opencode_prompt(message: str, req_id: str) -> str:
    message = (message or "").rstrip()
    return f"{REQ_ID_PREFIX} {req_id}\n\n{message}\n"


@dataclass(frozen=True)
class OpenCodeRequest:
    client_id: str
    work_dir: str
    timeout_s: float
    quiet: bool
    message: str
    req_id: str | None = None
    caller: str = "claude"


@dataclass(frozen=True)
class OpenCodeResult:
    exit_code: int
    reply: str
    req_id: str
    session_key: str
    done_seen: bool
    done_ms: int | None = None
