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
    runtime = _poll_runtime_state(submission)
    items = []

    reply, state = prepared.reader.try_get_message(state)
    _apply_session_rotation(
        submission,
        runtime,
        items,
        new_session_path=state_session_path_fn(state),
        provider_session_id=state.get("session_id"),
        now=now,
    )
    _emit_anchor(submission, runtime, items, now=now)

    if reply:
        _append_reply_item(
            submission,
            runtime,
            items,
            reply=reply,
            provider_session_id=state.get("session_id"),
            now=now,
            is_done_text_fn=is_done_text_fn,
            strip_done_text_fn=strip_done_text_fn,
        )

    updated = replace(
        submission,
        reply=runtime["reply_buffer"],
        runtime_state={
            **submission.runtime_state,
            "state": state,
            "next_seq": runtime["next_seq"],
            "anchor_emitted": runtime["anchor_emitted"],
            "reply_buffer": runtime["reply_buffer"],
            "session_path": runtime["session_path"],
        },
    )
    if not items:
        return None
    return ProviderPollResult(submission=updated, items=tuple(items))


def _poll_runtime_state(submission: ProviderSubmission) -> dict[str, object]:
    runtime_state = submission.runtime_state
    return {
        "request_anchor": request_anchor_from_runtime_state(
            runtime_state,
            fallback=submission.job_id,
        ),
        "next_seq": int(runtime_state.get("next_seq", 1)),
        "anchor_emitted": bool(runtime_state.get("anchor_emitted", False)),
        "reply_buffer": str(runtime_state.get("reply_buffer") or ""),
        "session_path": str(runtime_state.get("session_path") or ""),
    }


def _apply_session_rotation(
    submission: ProviderSubmission,
    runtime: dict[str, object],
    items: list,
    *,
    new_session_path: str | None,
    provider_session_id,
    now: str,
) -> None:
    session_path = str(runtime["session_path"])
    if not new_session_path or new_session_path == session_path:
        return
    items.append(
        build_item(
            submission,
            kind=CompletionItemKind.SESSION_ROTATE,
            timestamp=now,
            seq=int(runtime["next_seq"]),
            payload={
                "session_path": new_session_path,
                "provider_session_id": provider_session_id,
            },
            cursor_kwargs={"session_path": new_session_path},
        )
    )
    runtime["next_seq"] = int(runtime["next_seq"]) + 1
    runtime["session_path"] = new_session_path
    runtime["anchor_emitted"] = False
    runtime["reply_buffer"] = ""


def _emit_anchor(
    submission: ProviderSubmission,
    runtime: dict[str, object],
    items: list,
    *,
    now: str,
) -> None:
    if runtime["anchor_emitted"]:
        return
    session_path = str(runtime["session_path"] or "") or None
    items.append(
        build_item(
            submission,
            kind=CompletionItemKind.ANCHOR_SEEN,
            timestamp=now,
            seq=int(runtime["next_seq"]),
            payload={"turn_id": runtime["request_anchor"]},
            cursor_kwargs={"session_path": session_path},
        )
    )
    runtime["next_seq"] = int(runtime["next_seq"]) + 1
    runtime["anchor_emitted"] = True


def _append_reply_item(
    submission: ProviderSubmission,
    runtime: dict[str, object],
    items: list,
    *,
    reply,
    provider_session_id,
    now: str,
    is_done_text_fn,
    strip_done_text_fn,
) -> None:
    request_anchor = str(runtime["request_anchor"] or "") or None
    done_seen = bool(request_anchor and is_done_text_fn(str(reply), request_anchor))
    cleaned = _clean_reply(strip_done_text_fn, reply, request_anchor=request_anchor)
    if not cleaned:
        return
    runtime["reply_buffer"] = cleaned
    session_path = str(runtime["session_path"] or "") or None
    items.append(
        build_item(
            submission,
            kind=CompletionItemKind.ASSISTANT_FINAL,
            timestamp=now,
            seq=int(runtime["next_seq"]),
            payload={
                "text": cleaned,
                "reply": cleaned,
                "final_answer": cleaned,
                "turn_id": request_anchor,
                "session_path": session_path,
                "provider_session_id": provider_session_id,
                "done_marker": done_seen,
                "ccb_done": done_seen,
            },
            cursor_kwargs={"session_path": session_path},
        )
    )
    runtime["next_seq"] = int(runtime["next_seq"]) + 1


def _clean_reply(strip_done_text_fn, reply, *, request_anchor: str | None) -> str:
    if request_anchor:
        return strip_done_text_fn(str(reply), request_anchor).strip()
    return str(reply).strip()


__all__ = ["poll_submission"]
