from __future__ import annotations

from provider_execution.active import ensure_active_pane_alive, prepare_active_poll_without_liveness
from provider_execution.base import ProviderPollResult, ProviderSubmission

from .event_reading import is_turn_boundary_event, read_events, terminal_api_error_payload
from .hook_results import poll_exact_hook
from .state_machine import (
    apply_session_rotation,
    build_poll_state,
    finalize_poll_result,
    handle_assistant_event,
    handle_system_event,
    handle_user_event,
)
from .start import state_session_path


def poll_submission(adapter, submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
    del adapter
    prepared = prepare_active_poll_without_liveness(submission, now=now)
    if prepared is None or isinstance(prepared, ProviderPollResult):
        return prepared

    hook_result = poll_exact_hook(submission, now=now)
    if hook_result is not None:
        return hook_result

    pane_dead_result = ensure_active_pane_alive(submission, backend=prepared.backend, pane_id=prepared.pane_id, now=now)
    if pane_dead_result is not None:
        return pane_dead_result

    state = submission.runtime_state.get("state") or {}
    poll = build_poll_state(submission)

    while True:
        events, state = read_events(prepared.reader, state)
        new_session_path = state_session_path(state)
        apply_session_rotation(submission, poll, new_session_path=new_session_path, now=now)

        if not events:
            break

        for event in events:
            role = str(event.get("role") or "")
            if role == "user":
                handle_user_event(submission, poll, text=str(event.get("text") or ""), now=now)
                continue

            if role == "system":
                system_result = handle_system_event(submission, poll, event, now=now, state=state)
                if system_result is not None:
                    return system_result
                if poll.reached_turn_boundary:
                    break
                continue

            if role != "assistant" or not poll.anchor_seen:
                continue

            handle_assistant_event(submission, poll, event, now=now)
            if poll.reached_turn_boundary:
                break

        if poll.reached_turn_boundary:
            break

    return finalize_poll_result(submission, poll, state=state)


__all__ = [
    "is_turn_boundary_event",
    "poll_exact_hook",
    "poll_submission",
    "read_events",
    "terminal_api_error_payload",
]
