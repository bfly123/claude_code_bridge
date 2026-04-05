from __future__ import annotations

from provider_execution.active import prepare_active_poll
from provider_execution.base import ProviderPollResult, ProviderSubmission

from .event_reading import assistant_signature, read_entries
from .reply_logic import abort_status, clean_codex_reply_text, select_reply
from .state_machine import (
    apply_session_rotation,
    build_poll_state,
    finalize_poll_result,
    handle_assistant_entry,
    handle_terminal_entry,
    handle_user_entry,
    update_binding_refs,
)
from .start import state_session_path


def poll_submission(submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
    prepared = prepare_active_poll(submission, now=now)
    if prepared is None or isinstance(prepared, ProviderPollResult):
        return prepared

    state = submission.runtime_state.get('state') or {}
    poll = build_poll_state(submission)

    while True:
        entries, state = read_entries(prepared.reader, state)
        new_session_path = state_session_path(state)
        apply_session_rotation(submission, poll, new_session_path=new_session_path, now=now)

        if not entries:
            break

        for entry in entries:
            update_binding_refs(poll, entry)

            role = str(entry.get('role') or '').strip().lower()
            if role == 'user':
                handle_user_entry(submission, poll, text=str(entry.get("text") or ""), now=now)
                continue

            if not poll.anchor_seen:
                continue

            if role == 'assistant':
                handle_assistant_entry(submission, poll, entry, now=now)
                continue

            handle_terminal_entry(submission, poll, entry, now=now)
            if poll.reached_terminal:
                break

        if poll.reached_terminal:
            break

    return finalize_poll_result(submission, poll, state=state)


__all__ = [
    'abort_status',
    'assistant_signature',
    'clean_codex_reply_text',
    'poll_submission',
    'read_entries',
    'select_reply',
]
