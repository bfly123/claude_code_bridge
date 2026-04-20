from __future__ import annotations

from dataclasses import replace

from provider_execution.active import prepare_active_poll
from provider_execution.base import ProviderPollResult, ProviderSubmission

from .assistant import handle_assistant_event
from .state import apply_session_rotation, handle_user_event, poll_runtime_state


def _read_events(prepared, state, *, submission, runtime, items, state_session_path_fn, now: str):
    events, state = prepared.reader.try_get_events(state)
    apply_session_rotation(
        submission,
        runtime,
        items,
        new_session_path=state_session_path_fn(state),
        now=now,
    )
    return events, state


def _process_events(
    events,
    *,
    submission,
    runtime,
    items,
    now: str,
    is_done_text_fn,
    clean_reply_fn,
) -> bool:
    for role, text in events:
        if role == "user":
            handle_user_event(submission, runtime, items, text=text, now=now)
            continue
        if role != "assistant" or not runtime["anchor_seen"]:
            continue
        if not handle_assistant_event(
            submission,
            runtime,
            items,
            text=text,
            now=now,
            is_done_text_fn=is_done_text_fn,
            clean_reply_fn=clean_reply_fn,
        ):
            continue
        if runtime["done_seen"]:
            return True
    return False


def _polling_complete(runtime: dict[str, object]) -> bool:
    return bool(runtime["request_anchor"] and runtime["done_seen"])


def _updated_submission(submission: ProviderSubmission, *, state, runtime) -> ProviderSubmission:
    return replace(
        submission,
        reply=runtime["reply_buffer"],
        runtime_state={
            **submission.runtime_state,
            "state": state,
            "next_seq": runtime["next_seq"],
            "anchor_seen": runtime["anchor_seen"],
            "reply_buffer": runtime["reply_buffer"],
            "raw_buffer": runtime["raw_buffer"],
            "session_path": runtime["session_path"],
        },
    )


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
    runtime = poll_runtime_state(submission)
    items = []

    while True:
        events, state = _read_events(
            prepared,
            state,
            submission=submission,
            runtime=runtime,
            items=items,
            state_session_path_fn=state_session_path_fn,
            now=now,
        )

        if not events:
            break

        if _process_events(
            events,
            submission=submission,
            runtime=runtime,
            items=items,
            now=now,
            is_done_text_fn=is_done_text_fn,
            clean_reply_fn=clean_reply_fn,
        ):
            break

        if _polling_complete(runtime):
            break

    updated = _updated_submission(
        submission,
        state=state,
        runtime=runtime,
    )
    if not items:
        return None
    return ProviderPollResult(submission=updated, items=tuple(items))


__all__ = ['poll_submission']
