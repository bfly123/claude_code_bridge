from __future__ import annotations

from dataclasses import replace

from provider_execution.base import ProviderPollResult, ProviderSubmission

from .models import ClaudePollState


def finalize_poll_result(
    submission: ProviderSubmission,
    poll: ClaudePollState,
    *,
    state: dict[str, object],
) -> ProviderPollResult:
    updated = replace(
        submission,
        reply=poll.reply_buffer,
        runtime_state={
            **submission.runtime_state,
            "state": state,
            "next_seq": poll.next_seq,
            "anchor_seen": poll.anchor_seen,
            "reply_buffer": poll.reply_buffer,
            "raw_buffer": poll.raw_buffer,
            "session_path": poll.session_path,
            "last_assistant_uuid": poll.last_assistant_uuid,
        },
    )
    if not poll.items:
        return ProviderPollResult(submission=updated, items=())
    return ProviderPollResult(submission=updated, items=tuple(poll.items))


__all__ = ["finalize_poll_result"]
