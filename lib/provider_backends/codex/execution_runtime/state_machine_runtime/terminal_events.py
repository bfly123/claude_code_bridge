from __future__ import annotations

from completion.models import CompletionItemKind
from provider_execution.base import ProviderSubmission
from provider_execution.common import build_item

from ..reply_logic import abort_status, clean_codex_reply_text, select_reply
from .models import CodexPollState


def handle_terminal_entry(
    submission: ProviderSubmission,
    poll: CodexPollState,
    entry: dict[str, object],
    *,
    now: str,
) -> None:
    payload_type = str(entry.get("payload_type") or entry.get("entry_type") or "").strip().lower()
    if payload_type == "task_complete":
        terminal_text = str(entry.get("last_agent_message") or "").strip()
        if terminal_text:
            poll.last_agent_message = clean_codex_reply_text(terminal_text, poll.request_anchor).strip()
        reply = select_reply(
            last_agent_message=poll.last_agent_message,
            last_final_answer=poll.last_final_answer,
            last_assistant_message=poll.last_assistant_message,
            reply_buffer=poll.reply_buffer,
        )
        payload: dict[str, object] = {"reason": "task_complete", "last_agent_message": reply}
        if poll.bound_turn_id or poll.request_anchor:
            payload["turn_id"] = poll.bound_turn_id or poll.request_anchor
        if poll.bound_task_id:
            payload["task_id"] = poll.bound_task_id
        if poll.session_path:
            payload["session_path"] = poll.session_path
        poll.items.append(
            build_item(
                submission,
                kind=CompletionItemKind.TURN_BOUNDARY,
                timestamp=now,
                seq=poll.next_seq,
                payload=payload,
            )
        )
        poll.next_seq += 1
        poll.reached_terminal = True
        return

    if payload_type == "turn_aborted":
        reason = str(entry.get("reason") or "turn_aborted").strip() or "turn_aborted"
        error_text = str(entry.get("text") or "").strip()
        reply = select_reply(
            last_agent_message=poll.last_agent_message,
            last_final_answer=poll.last_final_answer,
            last_assistant_message=poll.last_assistant_message,
            reply_buffer=poll.reply_buffer,
        )
        payload: dict[str, object] = {
            "reason": reason,
            "status": abort_status(reason),
            "last_agent_message": reply,
        }
        if error_text:
            payload["text"] = error_text
            payload["error_message"] = error_text
        if poll.bound_turn_id or poll.request_anchor:
            payload["turn_id"] = poll.bound_turn_id or poll.request_anchor
        if poll.bound_task_id:
            payload["task_id"] = poll.bound_task_id
        if poll.session_path:
            payload["session_path"] = poll.session_path
        poll.items.append(
            build_item(
                submission,
                kind=CompletionItemKind.TURN_ABORTED,
                timestamp=now,
                seq=poll.next_seq,
                payload=payload,
            )
        )
        poll.next_seq += 1
        poll.reached_terminal = True


__all__ = ["handle_terminal_entry"]
