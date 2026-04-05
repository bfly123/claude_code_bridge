from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from completion.models import CompletionItem, CompletionItemKind
from provider_execution.base import ProviderSubmission
from provider_execution.common import build_item


@dataclass
class ClaudePollState:
    request_anchor: str
    next_seq: int
    anchor_seen: bool
    reply_buffer: str
    raw_buffer: str
    session_path: str
    last_assistant_uuid: str
    items: list[CompletionItem] = field(default_factory=list)
    reached_turn_boundary: bool = False


def build_poll_state(submission: ProviderSubmission) -> ClaudePollState:
    from provider_execution.common import request_anchor_from_runtime_state

    return ClaudePollState(
        request_anchor=request_anchor_from_runtime_state(submission.runtime_state, fallback=submission.job_id),
        next_seq=int(submission.runtime_state.get("next_seq", 1)),
        anchor_seen=bool(submission.runtime_state.get("anchor_seen", False)),
        reply_buffer=str(submission.runtime_state.get("reply_buffer") or ""),
        raw_buffer=str(submission.runtime_state.get("raw_buffer") or ""),
        session_path=str(submission.runtime_state.get("session_path") or ""),
        last_assistant_uuid=str(submission.runtime_state.get("last_assistant_uuid") or ""),
    )


def apply_session_rotation(submission: ProviderSubmission, poll: ClaudePollState, *, new_session_path: str, now: str) -> None:
    if not new_session_path or new_session_path == poll.session_path:
        return
    poll.items.append(
        build_item(
            submission,
            kind=CompletionItemKind.SESSION_ROTATE,
            timestamp=now,
            seq=poll.next_seq,
            payload={
                "session_path": new_session_path,
                "provider_session_id": Path(new_session_path).stem,
            },
        )
    )
    poll.next_seq += 1
    poll.session_path = new_session_path
    poll.anchor_seen = False
    poll.reply_buffer = ""
    poll.raw_buffer = ""
    poll.last_assistant_uuid = ""


__all__ = [
    "ClaudePollState",
    "apply_session_rotation",
    "build_poll_state",
]
