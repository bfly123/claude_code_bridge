from __future__ import annotations

from provider_core.protocol import DONE_PREFIX, REQ_ID_PREFIX
from provider_core.protocol_runtime.reply_runtime.extraction import extract_reply_for_req


def wrap_copilot_prompt(message: str, req_id: str) -> str:
    return "\n".join(prompt_sections(message, req_id=req_id)) + "\n"


def prompt_sections(message: str, *, req_id: str) -> list[str]:
    rendered = (message or "").rstrip()
    return [
        f"{REQ_ID_PREFIX} {req_id}",
        "",
        rendered,
        "",
        "IMPORTANT:",
        "- Reply with an execution summary, in English. Do not stay silent.",
        "- End your reply with this exact final line (verbatim, on its own line):",
        f"{DONE_PREFIX} {req_id}",
    ]
__all__ = ["extract_reply_for_req", "wrap_copilot_prompt"]
