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
    if is_duplicate_assistant_entry(poll, entry):
        return
    cleaned = cleaned_reply_text(entry, request_anchor=poll.request_anchor)
    if not cleaned:
        return

    poll.reply_buffer = append_reply_text(poll.reply_buffer, cleaned)
    poll.last_assistant_message = cleaned
    phase = entry_phase(entry)
    if phase == "final_answer":
        poll.last_final_answer = cleaned
    poll.items.append(
        build_item(
            submission,
            kind=CompletionItemKind.ASSISTANT_CHUNK,
            timestamp=now,
            seq=poll.next_seq,
            payload=assistant_payload(poll, cleaned=cleaned, phase=phase),
        )
    )
    poll.next_seq += 1


def is_duplicate_assistant_entry(poll: CodexPollState, entry: dict[str, object]) -> bool:
    signature = assistant_signature(entry)
    if not signature:
        return False
    if signature == poll.last_assistant_signature:
        return True
    poll.last_assistant_signature = signature
    return False


def cleaned_reply_text(entry: dict[str, object], *, request_anchor: str) -> str:
    return clean_codex_reply_text(str(entry.get("text") or ""), request_anchor).strip()


def append_reply_text(reply_buffer: str, cleaned: str) -> str:
    return f"{reply_buffer}\n{cleaned}".strip() if reply_buffer else cleaned


def entry_phase(entry: dict[str, object]) -> str:
    return str(entry.get("phase") or "").strip().lower()


def assistant_payload(poll: CodexPollState, *, cleaned: str, phase: str) -> dict[str, object]:
    payload: dict[str, object] = {
        "text": cleaned,
        "merged_text": poll.reply_buffer,
    }
    if poll.bound_turn_id:
        payload["turn_id"] = poll.bound_turn_id
    if poll.bound_task_id:
        payload["task_id"] = poll.bound_task_id
    if phase:
        payload["phase"] = phase
    if poll.session_path:
        payload["session_path"] = poll.session_path
    return payload


__all__ = ["handle_assistant_entry"]
