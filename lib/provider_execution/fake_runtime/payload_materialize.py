from __future__ import annotations

from completion.models import CompletionItemKind, CompletionStatus


TERMINAL_REPLY_KINDS = {
    CompletionItemKind.RESULT,
    CompletionItemKind.TURN_BOUNDARY,
}

TERMINAL_INFO_KINDS = {
    CompletionItemKind.CANCEL_INFO,
    CompletionItemKind.ERROR,
    CompletionItemKind.TURN_ABORTED,
    CompletionItemKind.PANE_DEAD,
}

SESSION_REPLY_KINDS = {
    CompletionItemKind.SESSION_SNAPSHOT,
    CompletionItemKind.SESSION_MUTATION,
}


def materialize_payload(
    kind: CompletionItemKind,
    payload: dict[str, object],
    *,
    reply_buffer: str,
    default_reply: str,
    turn_ref: str,
    terminal_reason: str,
) -> tuple[dict[str, object], str]:
    resolved = dict(payload)
    resolved.setdefault("turn_id", turn_ref)

    if kind is CompletionItemKind.ASSISTANT_CHUNK:
        return materialize_chunk_payload(
            resolved,
            reply_buffer=reply_buffer,
            default_reply=default_reply,
        )

    if kind is CompletionItemKind.ASSISTANT_FINAL:
        final_text = first_text(resolved, "text", "reply") or reply_buffer or default_reply
        resolved.setdefault("text", final_text)
        return resolved, final_text

    if kind in TERMINAL_REPLY_KINDS:
        final_reply = resolve_terminal_reply(
            resolved,
            reply_buffer=reply_buffer,
            default_reply=default_reply,
        )
        resolved.setdefault("reply", final_reply)
        resolved.setdefault("reason", terminal_reason)
        return resolved, final_reply

    if kind in TERMINAL_INFO_KINDS:
        resolved.setdefault("reason", terminal_reason)
        if kind is CompletionItemKind.TURN_ABORTED:
            resolved.setdefault("status", CompletionStatus.INCOMPLETE.value)
        if reply_buffer:
            resolved.setdefault("reply", reply_buffer)
        return resolved, reply_buffer

    if kind in SESSION_REPLY_KINDS:
        session_reply = resolve_session_reply(
            resolved,
            reply_buffer=reply_buffer,
            default_reply=default_reply,
        )
        resolved.setdefault("reply", session_reply)
        return resolved, session_reply

    return resolved, reply_buffer


def materialize_chunk_payload(
    payload: dict[str, object],
    *,
    reply_buffer: str,
    default_reply: str,
) -> tuple[dict[str, object], str]:
    chunk = first_text(payload, "text", "reply") or default_reply
    payload.setdefault("text", chunk)
    merged = first_text(payload, "merged_text")
    if merged:
        return payload, merged
    merged_text = reply_buffer + chunk
    payload["merged_text"] = merged_text
    return payload, merged_text


def resolve_terminal_reply(
    payload: dict[str, object],
    *,
    reply_buffer: str,
    default_reply: str,
) -> str:
    return (
        first_text(payload, "reply", "result_text", "final_answer", "text")
        or reply_buffer
        or default_reply
    )


def resolve_session_reply(
    payload: dict[str, object],
    *,
    reply_buffer: str,
    default_reply: str,
) -> str:
    return first_text(payload, "reply", "content", "text") or reply_buffer or default_reply


def first_text(payload: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


__all__ = ["first_text", "materialize_payload"]
