from __future__ import annotations

from provider_core.protocol import REQ_ID_PREFIX
from completion.models import CompletionItemKind
from provider_execution.base import ProviderSubmission
from provider_execution.common import build_item

from .models import CodexPollState


def handle_user_entry(
    submission: ProviderSubmission,
    poll: CodexPollState,
    *,
    text: str,
    now: str,
) -> None:
    if poll.request_anchor and f"{REQ_ID_PREFIX} {poll.request_anchor}" in text and not poll.anchor_seen:
        payload: dict[str, object] = {"turn_id": poll.bound_turn_id or poll.request_anchor}
        if poll.bound_task_id:
            payload["task_id"] = poll.bound_task_id
        if poll.session_path:
            payload["session_path"] = poll.session_path
        poll.items.append(
            build_item(
                submission,
                kind=CompletionItemKind.ANCHOR_SEEN,
                timestamp=now,
                seq=poll.next_seq,
                payload=payload,
            )
        )
        poll.next_seq += 1
        poll.anchor_seen = True


__all__ = ["handle_user_entry"]
