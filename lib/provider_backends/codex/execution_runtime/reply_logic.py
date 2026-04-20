from __future__ import annotations

from provider_core.protocol import strip_done_text


def select_reply(
    *,
    last_agent_message: str,
    last_final_answer: str,
    last_assistant_message: str,
    reply_buffer: str,
) -> str:
    for candidate in (last_agent_message, last_final_answer, last_assistant_message, reply_buffer):
        text = str(candidate or "").strip()
        if text:
            return text
    return ""


def clean_codex_reply_text(text: str, req_id: str) -> str:
    if not req_id:
        return str(text or "")
    return strip_done_text(str(text or ""), req_id)


def abort_status(reason: str) -> str:
    lowered = str(reason or "").strip().lower()
    if any(token in lowered for token in ("interrupt", "cancel", "abort")):
        return "cancelled"
    return "failed"


__all__ = ["abort_status", "clean_codex_reply_text", "select_reply"]
