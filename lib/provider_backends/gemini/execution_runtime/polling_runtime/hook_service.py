from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from completion.models import CompletionConfidence, CompletionCursor, CompletionDecision, CompletionItemKind, CompletionStatus
from provider_execution.base import ProviderPollResult
from provider_execution.common import build_item, request_anchor_from_runtime_state
from provider_hooks.artifacts import load_event

from .hook_payload import hook_decision_reason, hook_event_diagnostics, hook_item_payload


@dataclass(frozen=True)
class HookContext:
    completion_dir: str
    request_anchor: str
    next_seq: int


def poll_exact_hook(submission, *, now: str) -> ProviderPollResult | None:
    context = hook_context(submission)
    if context is None:
        return None
    event = load_event(context.completion_dir, context.request_anchor)
    if not event:
        return None
    reply = str(event.get('reply') or '').strip()
    cursor_path = hook_cursor_path(context)
    status = hook_status(event)
    diagnostics = hook_event_diagnostics(event)
    provider_turn_ref = hook_provider_turn_ref(event, request_anchor=context.request_anchor)
    item = build_hook_item(
        submission,
        event=event,
        context=context,
        cursor_path=cursor_path,
        reply=reply,
        status=status,
        provider_turn_ref=provider_turn_ref,
        diagnostics=diagnostics,
        now=now,
    )
    decision = build_hook_decision(
        submission,
        event=event,
        context=context,
        cursor_path=cursor_path,
        reply=reply,
        status=status,
        provider_turn_ref=provider_turn_ref,
        diagnostics=diagnostics,
        now=now,
    )
    updated = replace(
        submission,
        reply=reply,
        runtime_state={**submission.runtime_state, 'next_seq': context.next_seq + 1},
    )
    return ProviderPollResult(submission=updated, items=(item,), decision=decision)


def hook_context(submission) -> HookContext | None:
    completion_dir = str(submission.runtime_state.get('completion_dir') or '').strip()
    request_anchor = request_anchor_from_runtime_state(submission.runtime_state, fallback=submission.job_id)
    next_seq = int(submission.runtime_state.get('next_seq', 1))
    if not completion_dir or not request_anchor:
        return None
    return HookContext(
        completion_dir=completion_dir,
        request_anchor=request_anchor,
        next_seq=next_seq,
    )


def hook_cursor_path(context: HookContext) -> str:
    return str(Path(context.completion_dir) / 'events' / f'{context.request_anchor}.json')


def hook_status(event: dict[str, object]) -> CompletionStatus:
    return CompletionStatus(str(event.get('status') or CompletionStatus.COMPLETED.value))


def hook_provider_turn_ref(event: dict[str, object], *, request_anchor: str) -> str:
    return str(event.get('session_id') or request_anchor)


def hook_timestamp(event: dict[str, object], *, now: str) -> str:
    return str(event.get('timestamp') or now)


def build_hook_item(
    submission,
    *,
    event: dict[str, object],
    context: HookContext,
    cursor_path: str,
    reply: str,
    status: CompletionStatus,
    provider_turn_ref: str,
    diagnostics: dict[str, object],
    now: str,
):
    timestamp = hook_timestamp(event, now=now)
    return build_item(
        submission,
        kind=CompletionItemKind.ASSISTANT_FINAL,
        timestamp=timestamp,
        seq=context.next_seq,
        payload=hook_item_payload(
            req_id=context.request_anchor,
            reply=reply,
            status=status,
            provider_turn_ref=provider_turn_ref,
            hook_event_name=event.get('hook_event_name'),
            diagnostics=diagnostics,
        ),
        cursor_kwargs={'opaque_cursor': cursor_path},
    )


def build_hook_decision(
    submission,
    *,
    event: dict[str, object],
    context: HookContext,
    cursor_path: str,
    reply: str,
    status: CompletionStatus,
    provider_turn_ref: str,
    diagnostics: dict[str, object],
    now: str,
) -> CompletionDecision:
    timestamp = hook_timestamp(event, now=now)
    return CompletionDecision(
        terminal=True,
        status=status,
        reason=hook_decision_reason(status, diagnostics),
        confidence=CompletionConfidence.EXACT,
        reply=reply,
        anchor_seen=bool(submission.runtime_state.get('anchor_emitted', False)),
        reply_started=bool(reply),
        reply_stable=bool(reply),
        provider_turn_ref=provider_turn_ref,
        source_cursor=CompletionCursor(
            source_kind=submission.source_kind,
            opaque_cursor=cursor_path,
            event_seq=context.next_seq,
            updated_at=timestamp,
        ),
        finished_at=timestamp,
        diagnostics=diagnostics,
    )


__all__ = ['poll_exact_hook']
