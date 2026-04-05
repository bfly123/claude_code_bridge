from __future__ import annotations

from dataclasses import replace
from pathlib import Path

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
    clean_reply_fn,
) -> ProviderPollResult | None:
    prepared = prepare_active_poll(submission, now=now)
    if prepared is None or isinstance(prepared, ProviderPollResult):
        return prepared

    state = submission.runtime_state.get("state") or {}
    request_anchor = request_anchor_from_runtime_state(submission.runtime_state, fallback=submission.job_id)
    next_seq = int(submission.runtime_state.get("next_seq", 1))
    anchor_seen = bool(submission.runtime_state.get("anchor_seen", False))
    reply_buffer = str(submission.runtime_state.get("reply_buffer") or "")
    raw_buffer = str(submission.runtime_state.get("raw_buffer") or "")
    session_path = str(submission.runtime_state.get("session_path") or "")
    items = []

    while True:
        events, state = prepared.reader.try_get_events(state)
        new_session_path = state_session_path_fn(state)
        if new_session_path and new_session_path != session_path:
            items.append(
                build_item(
                    submission,
                    kind=CompletionItemKind.SESSION_ROTATE,
                    timestamp=now,
                    seq=next_seq,
                    payload={"session_path": new_session_path, "provider_session_id": Path(new_session_path).stem},
                    cursor_kwargs={"session_path": new_session_path},
                )
            )
            next_seq += 1
            session_path = new_session_path
            anchor_seen = False
            reply_buffer = ""
            raw_buffer = ""
        elif new_session_path:
            session_path = new_session_path

        if not events:
            break

        for role, text in events:
            if role == "user":
                if request_anchor and f"CCB_REQ_ID: {request_anchor}" in text and not anchor_seen:
                    items.append(
                        build_item(
                            submission,
                            kind=CompletionItemKind.ANCHOR_SEEN,
                            timestamp=now,
                            seq=next_seq,
                            payload={"turn_id": request_anchor, "session_path": session_path or None},
                            cursor_kwargs={"session_path": session_path or None},
                        )
                    )
                    next_seq += 1
                    anchor_seen = True
                continue

            if role != "assistant" or not anchor_seen:
                continue

            raw_buffer = f"{raw_buffer}\n{text}".strip() if raw_buffer else text
            done_seen = bool(request_anchor and is_done_text_fn(raw_buffer, request_anchor))
            cleaned = clean_reply_fn(raw_buffer, req_id=request_anchor)
            if not cleaned:
                continue

            reply_buffer = cleaned
            items.append(
                build_item(
                    submission,
                    kind=CompletionItemKind.ASSISTANT_FINAL if done_seen else CompletionItemKind.ASSISTANT_CHUNK,
                    timestamp=now,
                    seq=next_seq,
                    payload={
                        "text": cleaned,
                        "reply": cleaned,
                        "merged_text": cleaned,
                        "turn_id": request_anchor,
                        "session_path": session_path or None,
                        "done_marker": done_seen,
                        "ccb_done": done_seen,
                    },
                    cursor_kwargs={"session_path": session_path or None},
                )
            )
            next_seq += 1

            if done_seen:
                break

        if request_anchor and is_done_text_fn(raw_buffer, request_anchor):
            break

    updated = replace(
        submission,
        reply=reply_buffer,
        runtime_state={
            **submission.runtime_state,
            "state": state,
            "next_seq": next_seq,
            "anchor_seen": anchor_seen,
            "reply_buffer": reply_buffer,
            "raw_buffer": raw_buffer,
            "session_path": session_path,
        },
    )
    if not items:
        return None
    return ProviderPollResult(submission=updated, items=tuple(items))


__all__ = ["poll_submission"]
