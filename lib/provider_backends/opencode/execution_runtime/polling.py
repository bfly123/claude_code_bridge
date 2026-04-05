from __future__ import annotations

from dataclasses import replace

from completion.models import CompletionItemKind
from provider_execution.active import prepare_active_poll
from provider_execution.base import ProviderPollResult, ProviderSubmission
from provider_execution.common import build_item, request_anchor_from_runtime_state


def poll_submission(
    submission: ProviderSubmission,
    *,
    now: str,
    state_session_path_fn,
    is_done_text_fn,
    strip_done_text_fn,
) -> ProviderPollResult | None:
    prepared = prepare_active_poll(submission, now=now)
    if prepared is None or isinstance(prepared, ProviderPollResult):
        return prepared

    state = submission.runtime_state.get("state") or {}
    next_seq = int(submission.runtime_state.get("next_seq", 1))
    anchor_emitted = bool(submission.runtime_state.get("anchor_emitted", False))
    reply_buffer = str(submission.runtime_state.get("reply_buffer") or "")
    session_path = str(submission.runtime_state.get("session_path") or "")
    items = []

    reply, state = prepared.reader.try_get_message(state)
    new_session_path = state_session_path_fn(state)
    if new_session_path and new_session_path != session_path:
        items.append(
            build_item(
                submission,
                kind=CompletionItemKind.SESSION_ROTATE,
                timestamp=now,
                seq=next_seq,
                payload={"session_path": new_session_path, "provider_session_id": state.get("session_id")},
                cursor_kwargs={"session_path": new_session_path},
            )
        )
        next_seq += 1
        session_path = new_session_path
        anchor_emitted = False
        reply_buffer = ""

    if not anchor_emitted:
        request_anchor = request_anchor_from_runtime_state(submission.runtime_state, fallback=submission.job_id)
        items.append(
            build_item(
                submission,
                kind=CompletionItemKind.ANCHOR_SEEN,
                timestamp=now,
                seq=next_seq,
                payload={"turn_id": request_anchor},
                cursor_kwargs={"session_path": session_path or None},
            )
        )
        next_seq += 1
        anchor_emitted = True

    if reply:
        request_anchor = request_anchor_from_runtime_state(submission.runtime_state, fallback=submission.job_id)
        done_seen = bool(request_anchor and is_done_text_fn(str(reply), request_anchor))
        cleaned = strip_done_text_fn(str(reply), request_anchor).strip() if request_anchor else str(reply).strip()
        if cleaned:
            reply_buffer = cleaned
            items.append(
                build_item(
                    submission,
                    kind=CompletionItemKind.ASSISTANT_FINAL,
                    timestamp=now,
                    seq=next_seq,
                    payload={
                        "text": cleaned,
                        "reply": cleaned,
                        "final_answer": cleaned,
                        "turn_id": request_anchor,
                        "session_path": session_path or None,
                        "provider_session_id": state.get("session_id"),
                        "done_marker": done_seen,
                        "ccb_done": done_seen,
                    },
                    cursor_kwargs={"session_path": session_path or None},
                )
            )
            next_seq += 1

    updated = replace(
        submission,
        reply=reply_buffer,
        runtime_state={
            **submission.runtime_state,
            "state": state,
            "next_seq": next_seq,
            "anchor_emitted": anchor_emitted,
            "reply_buffer": reply_buffer,
            "session_path": session_path,
        },
    )
    if not items:
        return None
    return ProviderPollResult(submission=updated, items=tuple(items))


__all__ = ["poll_submission"]
