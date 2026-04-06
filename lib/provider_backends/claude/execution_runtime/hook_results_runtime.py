from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from completion.models import (
    CompletionConfidence,
    CompletionCursor,
    CompletionDecision,
    CompletionItemKind,
    CompletionStatus,
)
from provider_execution.base import ProviderPollResult, ProviderSubmission
from provider_execution.common import build_item, request_anchor_from_runtime_state
from provider_hooks.artifacts import load_event


@dataclass(frozen=True)
class HookPollContext:
    completion_dir: str
    request_anchor: str
    next_seq: int


def poll_exact_hook(submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
    context = hook_poll_context(submission)
    if context is None:
        return None
    event = load_event(context.completion_dir, context.request_anchor)
    if not event:
        return None

    reply = hook_reply(event)
    status = hook_status(event)
    provider_turn_ref = hook_provider_turn_ref(event, request_anchor=context.request_anchor)
    cursor_path = hook_cursor_path(context)
    item = build_hook_item(
        submission,
        event=event,
        context=context,
        reply=reply,
        status=status,
        provider_turn_ref=provider_turn_ref,
        cursor_path=cursor_path,
        now=now,
    )
    decision = build_hook_decision(
        submission,
        event=event,
        context=context,
        reply=reply,
        status=status,
        provider_turn_ref=provider_turn_ref,
        cursor_path=cursor_path,
        now=now,
    )
    updated = advance_submission(submission, reply=reply, next_seq=context.next_seq + 1)
    return ProviderPollResult(submission=updated, items=(item,), decision=decision)


def hook_poll_context(submission: ProviderSubmission) -> HookPollContext | None:
    completion_dir = str(submission.runtime_state.get("completion_dir") or "").strip()
    request_anchor = request_anchor_from_runtime_state(submission.runtime_state, fallback=submission.job_id)
    next_seq = int(submission.runtime_state.get("next_seq", 1))
    if not completion_dir or not request_anchor:
        return None
    return HookPollContext(
        completion_dir=completion_dir,
        request_anchor=request_anchor,
        next_seq=next_seq,
    )


def hook_reply(event: dict[str, object]) -> str:
    return str(event.get("reply") or "").strip()


def hook_status(event: dict[str, object]) -> CompletionStatus:
    return CompletionStatus(str(event.get("status") or CompletionStatus.COMPLETED.value))


def hook_provider_turn_ref(event: dict[str, object], *, request_anchor: str) -> str:
    return str(event.get("session_id") or request_anchor)


def hook_cursor_path(context: HookPollContext) -> str:
    return str(Path(context.completion_dir) / "events" / f"{context.request_anchor}.json")


def hook_timestamp(event: dict[str, object], *, now: str) -> str:
    return str(event.get("timestamp") or now)


def hook_item_payload(
    *,
    event: dict[str, object],
    reply: str,
    request_anchor: str,
    provider_turn_ref: str,
    status: CompletionStatus,
) -> dict[str, object]:
    return {
        "reply": reply,
        "text": reply,
        "turn_id": request_anchor,
        "provider_turn_ref": provider_turn_ref,
        "completion_source": "hook_artifact",
        "hook_event_name": event.get("hook_event_name"),
        "status": status.value,
    }


def hook_diagnostics(event: dict[str, object]) -> dict[str, object]:
    return {
        "completion_source": "hook_artifact",
        "hook_event_name": event.get("hook_event_name"),
    }


def hook_reason(status: CompletionStatus) -> str:
    if status is CompletionStatus.FAILED:
        return "hook_stop_failure"
    return "hook_stop"


def build_hook_item(
    submission: ProviderSubmission,
    *,
    event: dict[str, object],
    context: HookPollContext,
    reply: str,
    status: CompletionStatus,
    provider_turn_ref: str,
    cursor_path: str,
    now: str,
):
    return build_item(
        submission,
        kind=CompletionItemKind.ASSISTANT_FINAL,
        timestamp=hook_timestamp(event, now=now),
        seq=context.next_seq,
        payload=hook_item_payload(
            event=event,
            reply=reply,
            request_anchor=context.request_anchor,
            provider_turn_ref=provider_turn_ref,
            status=status,
        ),
        cursor_kwargs={"opaque_cursor": cursor_path},
    )


def build_hook_decision(
    submission: ProviderSubmission,
    *,
    event: dict[str, object],
    context: HookPollContext,
    reply: str,
    status: CompletionStatus,
    provider_turn_ref: str,
    cursor_path: str,
    now: str,
) -> CompletionDecision:
    timestamp = hook_timestamp(event, now=now)
    return CompletionDecision(
        terminal=True,
        status=status,
        reason=hook_reason(status),
        confidence=CompletionConfidence.EXACT,
        reply=reply,
        anchor_seen=bool(submission.runtime_state.get("anchor_seen", False)),
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
        diagnostics=hook_diagnostics(event),
    )


def advance_submission(submission: ProviderSubmission, *, reply: str, next_seq: int) -> ProviderSubmission:
    return replace(
        submission,
        reply=reply,
        runtime_state={**submission.runtime_state, "next_seq": next_seq},
    )


__all__ = ["poll_exact_hook"]
