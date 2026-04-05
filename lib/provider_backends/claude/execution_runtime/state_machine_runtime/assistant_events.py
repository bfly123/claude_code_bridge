from __future__ import annotations

from completion.models import CompletionItemKind
from provider_execution.base import ProviderSubmission
from provider_execution.common import build_item

from ...protocol import extract_reply_for_req, is_done_text, strip_done_text
from .models import ClaudePollState


def handle_assistant_event(
    submission: ProviderSubmission,
    poll: ClaudePollState,
    event: dict[str, object],
    *,
    now: str,
) -> None:
    text = str(event.get("text") or "")
    subagent_id = str(event.get("subagent_id") or "").strip()
    subagent_name = str(event.get("subagent_name") or "").strip()
    is_subagent = bool(subagent_id or subagent_name)
    event_assistant_uuid = str(event.get("uuid") or "").strip()
    poll.raw_buffer = f"{poll.raw_buffer}\n{text}".strip() if poll.raw_buffer else text
    cleaned = strip_done_text(text, poll.request_anchor) if poll.request_anchor else text
    if cleaned.strip():
        poll.reply_buffer = f"{poll.reply_buffer}\n{cleaned}".strip() if poll.reply_buffer else cleaned
        if not is_subagent:
            poll.last_assistant_uuid = str(event_assistant_uuid or poll.last_assistant_uuid or "")
        poll.items.append(
            build_item(
                submission,
                kind=CompletionItemKind.ASSISTANT_CHUNK,
                timestamp=now,
                seq=poll.next_seq,
                payload={
                    "text": cleaned,
                    "merged_text": poll.reply_buffer,
                    "turn_id": poll.request_anchor,
                    "session_path": poll.session_path or None,
                    "assistant_uuid": event_assistant_uuid or poll.last_assistant_uuid or None,
                    "subagent_id": subagent_id or None,
                    "subagent_name": subagent_name or None,
                    "stop_reason": event.get("stop_reason"),
                },
            )
        )
        poll.next_seq += 1

    if poll.request_anchor and is_done_text(poll.raw_buffer, poll.request_anchor):
        reply = extract_reply_for_req(poll.raw_buffer, poll.request_anchor) or poll.reply_buffer
        poll.items.append(
            build_item(
                submission,
                kind=CompletionItemKind.TURN_BOUNDARY,
                timestamp=now,
                seq=poll.next_seq,
                payload={
                    "reason": "task_complete",
                    "last_agent_message": reply,
                    "turn_id": poll.request_anchor,
                    "session_path": poll.session_path or None,
                    "assistant_uuid": poll.last_assistant_uuid or None,
                },
            )
        )
        poll.next_seq += 1
        poll.reached_turn_boundary = True


__all__ = ["handle_assistant_event"]
