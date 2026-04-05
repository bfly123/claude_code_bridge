from __future__ import annotations

from completion.models import CompletionItemKind
from provider_execution.base import ProviderSubmission
from provider_execution.common import build_item

from ..event_reading import assistant_signature
from ..reply_logic import clean_codex_reply_text
from .models import CodexPollState


def handle_assistant_entry(
    submission: ProviderSubmission,
    poll: CodexPollState,
    entry: dict[str, object],
    *,
    now: str,
) -> None:
    signature = assistant_signature(entry)
    if signature and signature == poll.last_assistant_signature:
        return
    if signature:
        poll.last_assistant_signature = signature

    cleaned = clean_codex_reply_text(str(entry.get("text") or ""), poll.request_anchor).strip()
    if not cleaned:
        return

    poll.reply_buffer = f"{poll.reply_buffer}\n{cleaned}".strip() if poll.reply_buffer else cleaned
    poll.last_assistant_message = cleaned
    phase = str(entry.get("phase") or "").strip().lower()
    if phase == "final_answer":
        poll.last_final_answer = cleaned

    payload: dict[str, object] = {"text": cleaned, "merged_text": poll.reply_buffer}
    if poll.bound_turn_id:
        payload["turn_id"] = poll.bound_turn_id
    if poll.bound_task_id:
        payload["task_id"] = poll.bound_task_id
    if phase:
        payload["phase"] = phase
    if poll.session_path:
        payload["session_path"] = poll.session_path
    poll.items.append(
        build_item(
            submission,
            kind=CompletionItemKind.ASSISTANT_CHUNK,
            timestamp=now,
            seq=poll.next_seq,
            payload=payload,
        )
    )
    poll.next_seq += 1


__all__ = ["handle_assistant_entry"]
