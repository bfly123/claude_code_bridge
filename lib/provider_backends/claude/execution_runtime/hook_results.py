from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from completion.models import (
    CompletionConfidence,
    CompletionCursor,
    CompletionDecision,
    CompletionItemKind,
    CompletionStatus,
)
from provider_hooks.artifacts import load_event
from provider_execution.base import ProviderPollResult, ProviderSubmission
from provider_execution.common import build_item, request_anchor_from_runtime_state


def poll_exact_hook(submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
    completion_dir = str(submission.runtime_state.get("completion_dir") or "").strip()
    request_anchor = request_anchor_from_runtime_state(submission.runtime_state, fallback=submission.job_id)
    next_seq = int(submission.runtime_state.get("next_seq", 1))
    if not completion_dir or not request_anchor:
        return None
    event = load_event(completion_dir, request_anchor)
    if not event:
        return None
    reply = str(event.get("reply") or "").strip()
    item = build_item(
        submission,
        kind=CompletionItemKind.ASSISTANT_FINAL,
        timestamp=str(event.get("timestamp") or now),
        seq=next_seq,
        payload={
            "reply": reply,
            "text": reply,
            "turn_id": request_anchor,
            "provider_turn_ref": str(event.get("session_id") or request_anchor),
            "completion_source": "hook_artifact",
            "hook_event_name": event.get("hook_event_name"),
            "status": event.get("status"),
        },
        cursor_kwargs={"opaque_cursor": str(Path(completion_dir) / "events" / f"{request_anchor}.json")},
    )
    status = CompletionStatus(str(event.get("status") or CompletionStatus.COMPLETED.value))
    reason = "hook_stop"
    if status is CompletionStatus.FAILED:
        reason = "hook_stop_failure"
    decision = CompletionDecision(
        terminal=True,
        status=status,
        reason=reason,
        confidence=CompletionConfidence.EXACT,
        reply=reply,
        anchor_seen=bool(submission.runtime_state.get("anchor_seen", False)),
        reply_started=bool(reply),
        reply_stable=bool(reply),
        provider_turn_ref=str(event.get("session_id") or request_anchor),
        source_cursor=CompletionCursor(
            source_kind=submission.source_kind,
            opaque_cursor=str(Path(completion_dir) / "events" / f"{request_anchor}.json"),
            event_seq=next_seq,
            updated_at=str(event.get("timestamp") or now),
        ),
        finished_at=str(event.get("timestamp") or now),
        diagnostics={"completion_source": "hook_artifact", "hook_event_name": event.get("hook_event_name")},
    )
    updated = replace(
        submission,
        reply=reply,
        runtime_state={**submission.runtime_state, "next_seq": next_seq + 1},
    )
    return ProviderPollResult(submission=updated, items=(item,), decision=decision)


__all__ = ["poll_exact_hook"]
