from __future__ import annotations

from completion.models import CompletionCursor, CompletionItem, CompletionItemKind

from provider_execution.base import ProviderSubmission


def build_item(
    submission: ProviderSubmission,
    *,
    kind: CompletionItemKind,
    timestamp: str,
    seq: int,
    payload: dict[str, object],
    cursor_kwargs: dict[str, object] | None = None,
) -> CompletionItem:
    cursor_payload = {'source_kind': submission.source_kind, 'event_seq': seq, 'updated_at': timestamp}
    if cursor_kwargs:
        cursor_payload.update(cursor_kwargs)
    return CompletionItem(
        kind=kind,
        timestamp=timestamp,
        cursor=CompletionCursor(**cursor_payload),
        provider=submission.provider,
        agent_name=submission.agent_name,
        req_id=submission.job_id,
        payload=payload,
    )


def request_anchor_from_runtime_state(runtime_state: dict[str, object] | None, *, fallback: str | None = None) -> str:
    if not isinstance(runtime_state, dict):
        return str(fallback or '').strip()
    return str(runtime_state.get('request_anchor') or runtime_state.get('req_id') or fallback or '').strip()


__all__ = ['build_item', 'request_anchor_from_runtime_state']
