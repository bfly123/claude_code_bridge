from __future__ import annotations

from completion.models import CompletionItemKind
from provider_execution.base import ProviderSubmission
from provider_execution.common import build_item


def handle_assistant_event(
    submission: ProviderSubmission,
    runtime: dict[str, object],
    items: list,
    *,
    text: str,
    now: str,
    is_done_text_fn,
    clean_reply_fn,
) -> bool:
    raw_buffer = merged_reply_text(str(runtime["raw_buffer"]), text)
    runtime["raw_buffer"] = raw_buffer
    request_anchor = str(runtime["request_anchor"] or "") or None
    done_seen = bool(request_anchor and is_done_text_fn(raw_buffer, request_anchor))
    runtime["done_seen"] = done_seen
    cleaned = clean_reply_fn(raw_buffer, req_id=request_anchor)
    if not cleaned:
        return False
    runtime["reply_buffer"] = cleaned
    items.append(
        assistant_reply_item(
            submission,
            runtime,
            cleaned=cleaned,
            done_seen=done_seen,
            now=now,
        )
    )
    runtime["next_seq"] = int(runtime["next_seq"]) + 1
    return True


def assistant_reply_item(
    submission: ProviderSubmission,
    runtime: dict[str, object],
    *,
    cleaned: str,
    done_seen: bool,
    now: str,
):
    session_path = str(runtime["session_path"] or "") or None
    request_anchor = str(runtime["request_anchor"] or "") or None
    return build_item(
        submission,
        kind=(
            CompletionItemKind.ASSISTANT_FINAL
            if done_seen
            else CompletionItemKind.ASSISTANT_CHUNK
        ),
        timestamp=now,
        seq=int(runtime["next_seq"]),
        payload={
            "text": cleaned,
            "reply": cleaned,
            "merged_text": cleaned,
            "turn_id": request_anchor,
            "session_path": session_path,
            "done_marker": done_seen,
            "ccb_done": done_seen,
        },
        cursor_kwargs={"session_path": session_path},
    )


def merged_reply_text(raw_buffer: str, text: str) -> str:
    return f"{raw_buffer}\n{text}".strip() if raw_buffer else text


__all__ = ['handle_assistant_event']
