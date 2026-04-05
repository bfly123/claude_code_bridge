from __future__ import annotations

from dataclasses import replace

from completion.models import CompletionConfidence, CompletionDecision, CompletionStatus
from completion.models import CompletionItemKind

from ..base import ProviderPollResult, ProviderSubmission
from ..common import build_item, is_runtime_target_alive
from .models import PreparedActivePoll


def prepare_active_poll(submission: ProviderSubmission, *, now: str) -> ProviderPollResult | PreparedActivePoll | None:
    return _prepare_active_poll(submission, now=now, check_pane_alive=True)


def prepare_active_poll_without_liveness(
    submission: ProviderSubmission,
    *,
    now: str,
) -> ProviderPollResult | PreparedActivePoll | None:
    return _prepare_active_poll(submission, now=now, check_pane_alive=False)


def _prepare_active_poll(
    submission: ProviderSubmission,
    *,
    now: str,
    check_pane_alive: bool,
) -> ProviderPollResult | PreparedActivePoll | None:
    mode = str(submission.runtime_state.get("mode") or "passive")
    if mode == "passive":
        return _runtime_error_result(
            submission,
            now=now,
            reason=str(submission.runtime_state.get("reason") or "runtime_unavailable"),
            error=str(submission.runtime_state.get("error") or ""),
        )

    if mode == "error":
        return _runtime_error_result(
            submission,
            now=now,
            reason=str(submission.runtime_state.get("reason") or "transport_error"),
            error=str(submission.runtime_state.get("error") or ""),
        )

    reader = submission.runtime_state.get("reader")
    backend = submission.runtime_state.get("backend")
    pane_id = str(submission.runtime_state.get("pane_id") or "")
    if reader is None or backend is None or not pane_id:
        return _runtime_error_result(
            submission,
            now=now,
            reason="runtime_state_corrupt",
        )

    if check_pane_alive:
        result = ensure_active_pane_alive(submission, backend=backend, pane_id=pane_id, now=now)
        if result is not None:
            return result

    return PreparedActivePoll(reader=reader, backend=backend, pane_id=pane_id)


def ensure_active_pane_alive(
    submission: ProviderSubmission,
    *,
    backend: object,
    pane_id: str,
    now: str,
) -> ProviderPollResult | None:
    try:
        pane_alive = is_runtime_target_alive(backend, pane_id)
    except Exception:
        pane_alive = False
    if pane_alive:
        return None
    item = build_item(
        submission,
        kind=CompletionItemKind.PANE_DEAD,
        timestamp=now,
        seq=int(submission.runtime_state.get("next_seq", 1)),
        payload={"reason": "pane_dead"},
    )
    updated = replace(
        submission,
        runtime_state={**submission.runtime_state, "mode": "passive", "next_seq": item.cursor.event_seq + 1},
    )
    return ProviderPollResult(
        submission=updated,
        items=(item,),
        decision=CompletionDecision(
            terminal=True,
            status=CompletionStatus.FAILED,
            reason="pane_dead",
            confidence=CompletionConfidence.DEGRADED,
            reply="",
            anchor_seen=False,
            reply_started=False,
            reply_stable=False,
            provider_turn_ref=None,
            source_cursor=item.cursor,
            finished_at=now,
            diagnostics={"reason": "pane_dead"},
        ),
    )


def _runtime_error_result(
    submission: ProviderSubmission,
    *,
    now: str,
    reason: str,
    error: str = "",
) -> ProviderPollResult:
    item = build_item(
        submission,
        kind=CompletionItemKind.ERROR,
        timestamp=now,
        seq=int(submission.runtime_state.get("next_seq", 1)),
        payload={"reason": reason or "transport_error", "error": error or ""},
    )
    updated = replace(
        submission,
        runtime_state={**submission.runtime_state, "mode": "passive", "next_seq": item.cursor.event_seq + 1},
    )
    diagnostics = {"reason": reason or "transport_error"}
    if error:
        diagnostics["error"] = error
        diagnostics["error_message"] = error
    return ProviderPollResult(
        submission=updated,
        items=(item,),
        decision=CompletionDecision(
            terminal=True,
            status=CompletionStatus.FAILED,
            reason=reason or "transport_error",
            confidence=CompletionConfidence.DEGRADED,
            reply="",
            anchor_seen=False,
            reply_started=False,
            reply_stable=False,
            provider_turn_ref=None,
            source_cursor=item.cursor,
            finished_at=now,
            diagnostics=diagnostics,
        ),
    )


__all__ = [
    "ensure_active_pane_alive",
    "prepare_active_poll",
    "prepare_active_poll_without_liveness",
]
