from __future__ import annotations

from pathlib import Path

from completion.models import CompletionItemKind
from provider_execution.base import ProviderSubmission
from provider_execution.common import build_item, request_anchor_from_runtime_state


def poll_runtime_state(submission: ProviderSubmission) -> dict[str, object]:
    runtime_state = submission.runtime_state
    return {
        "request_anchor": request_anchor_from_runtime_state(
            runtime_state,
            fallback=submission.job_id,
        ),
        "next_seq": int(runtime_state.get("next_seq", 1)),
        "anchor_seen": bool(runtime_state.get("anchor_seen", False)),
        "reply_buffer": str(runtime_state.get("reply_buffer") or ""),
        "raw_buffer": str(runtime_state.get("raw_buffer") or ""),
        "session_path": str(runtime_state.get("session_path") or ""),
        "done_seen": False,
    }


def apply_session_rotation(
    submission: ProviderSubmission,
    runtime: dict[str, object],
    items: list,
    *,
    new_session_path: str | None,
    now: str,
) -> None:
    session_path = str(runtime["session_path"])
    if not new_session_path:
        return
    if new_session_path == session_path:
        runtime["session_path"] = new_session_path
        return
    items.append(
        session_rotate_item(
            submission,
            runtime,
            new_session_path=new_session_path,
            now=now,
        )
    )
    runtime["next_seq"] = int(runtime["next_seq"]) + 1
    runtime["session_path"] = new_session_path
    runtime["anchor_seen"] = False
    runtime["reply_buffer"] = ""
    runtime["raw_buffer"] = ""
    runtime["done_seen"] = False


def session_rotate_item(
    submission: ProviderSubmission,
    runtime: dict[str, object],
    *,
    new_session_path: str,
    now: str,
):
    return build_item(
        submission,
        kind=CompletionItemKind.SESSION_ROTATE,
        timestamp=now,
        seq=int(runtime["next_seq"]),
        payload={
            "session_path": new_session_path,
            "provider_session_id": Path(new_session_path).stem,
        },
        cursor_kwargs={"session_path": new_session_path},
    )


def handle_user_event(
    submission: ProviderSubmission,
    runtime: dict[str, object],
    items: list,
    *,
    text: str,
    now: str,
) -> None:
    request_anchor = str(runtime["request_anchor"] or "")
    if not request_anchor or runtime["anchor_seen"]:
        return
    if f"CCB_REQ_ID: {request_anchor}" not in text:
        return
    session_path = str(runtime["session_path"] or "") or None
    items.append(
        build_item(
            submission,
            kind=CompletionItemKind.ANCHOR_SEEN,
            timestamp=now,
            seq=int(runtime["next_seq"]),
            payload={"turn_id": request_anchor, "session_path": session_path},
            cursor_kwargs={"session_path": session_path},
        )
    )
    runtime["next_seq"] = int(runtime["next_seq"]) + 1
    runtime["anchor_seen"] = True


__all__ = ['apply_session_rotation', 'handle_user_event', 'poll_runtime_state']
