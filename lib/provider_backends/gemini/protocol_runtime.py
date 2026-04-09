from __future__ import annotations

from provider_core.protocol import DONE_PREFIX, REQ_ID_PREFIX
from provider_core.protocol_runtime.reply_runtime.extraction import extract_reply_for_req


def wrap_gemini_prompt(message: str, req_id: str) -> str:
    return "\n".join(prompt_sections(message, req_id=req_id)) + "\n"


def wrap_gemini_turn_prompt(message: str, req_id: str) -> str:
    rendered = (message or "").rstrip()
    return "\n".join(
        [
            f"{REQ_ID_PREFIX} {req_id}",
            "",
            rendered,
        ]
    ) + "\n"


def prompt_sections(message: str, *, req_id: str) -> list[str]:
    rendered = (message or "").rstrip()
    return [
        f"{REQ_ID_PREFIX} {req_id}",
        "",
        rendered,
        "",
        "IMPORTANT — you MUST follow these rules:",
        "1. Reply in English with an execution summary. Do not stay silent.",
        "2. Your FINAL line MUST be exactly (copy verbatim, no extra text):",
        f"   {DONE_PREFIX} {req_id}",
        "3. Do NOT omit, modify, or paraphrase the line above.",
    ]
__all__ = ["extract_reply_for_req", "wrap_gemini_prompt", "wrap_gemini_turn_prompt"]
