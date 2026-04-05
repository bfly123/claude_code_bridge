from __future__ import annotations

from completion.models import (
    CompletionConfidence,
    CompletionCursor,
    CompletionDecision,
    CompletionItemKind,
    CompletionStatus,
)

from provider_execution.base import ProviderSubmission


def build_terminal_decision(
    submission: ProviderSubmission,
    *,
    payload: dict[str, object],
    cursor: CompletionCursor,
    finished_at: str,
    reply: str,
) -> CompletionDecision:
    status = CompletionStatus(str(payload.get('status') or submission.status.value))
    confidence = CompletionConfidence(str(payload.get('confidence') or submission.confidence.value))
    reason = str(payload.get('reason') or submission.reason)
    diagnostics = dict(submission.diagnostics or {})
    diagnostics['fake_terminal_kind'] = str(payload.get('kind') or '')
    return CompletionDecision(
        terminal=True,
        status=status,
        reason=reason,
        confidence=confidence,
        reply=reply,
        anchor_seen=False,
        reply_started=False,
        reply_stable=False,
        provider_turn_ref=str(payload.get('turn_id') or submission.job_id),
        source_cursor=cursor,
        finished_at=finished_at,
        diagnostics=diagnostics,
    )


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
    resolved.setdefault('turn_id', turn_ref)

    if kind is CompletionItemKind.ASSISTANT_CHUNK:
        chunk = first_text(resolved, 'text', 'reply') or default_reply
        resolved.setdefault('text', chunk)
        merged = first_text(resolved, 'merged_text')
        if merged:
            reply_buffer = merged
        else:
            reply_buffer = reply_buffer + chunk
            resolved['merged_text'] = reply_buffer
        return resolved, reply_buffer

    if kind is CompletionItemKind.ASSISTANT_FINAL:
        final_text = first_text(resolved, 'text', 'reply') or reply_buffer or default_reply
        resolved.setdefault('text', final_text)
        return resolved, final_text

    if kind in {CompletionItemKind.RESULT, CompletionItemKind.TURN_BOUNDARY}:
        final_reply = first_text(resolved, 'reply', 'result_text', 'final_answer', 'text') or reply_buffer or default_reply
        resolved.setdefault('reply', final_reply)
        resolved.setdefault('reason', terminal_reason)
        return resolved, final_reply

    if kind in {CompletionItemKind.CANCEL_INFO, CompletionItemKind.ERROR, CompletionItemKind.TURN_ABORTED, CompletionItemKind.PANE_DEAD}:
        resolved.setdefault('reason', terminal_reason)
        if kind is CompletionItemKind.TURN_ABORTED:
            resolved.setdefault('status', CompletionStatus.INCOMPLETE.value)
        if reply_buffer:
            resolved.setdefault('reply', reply_buffer)
        return resolved, reply_buffer

    if kind in {CompletionItemKind.SESSION_SNAPSHOT, CompletionItemKind.SESSION_MUTATION}:
        session_reply = first_text(resolved, 'reply', 'content', 'text') or reply_buffer or default_reply
        resolved.setdefault('reply', session_reply)
        return resolved, session_reply

    return resolved, reply_buffer


def first_text(payload: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


__all__ = ['build_terminal_decision', 'first_text', 'materialize_payload']
