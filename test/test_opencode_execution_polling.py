from __future__ import annotations

from types import SimpleNamespace

from completion.models import CompletionItemKind, CompletionSourceKind
from provider_backends.opencode.execution_runtime.polling import poll_submission
from provider_execution.base import ProviderSubmission


def _submission() -> ProviderSubmission:
    return ProviderSubmission(
        job_id="job_1",
        agent_name="agent1",
        provider="opencode",
        accepted_at="2026-04-06T00:00:00Z",
        ready_at="2026-04-06T00:00:00Z",
        source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
        reply="",
        runtime_state={"state": {}, "next_seq": 1},
    )


def test_opencode_poll_submission_emits_rotate_anchor_and_final(monkeypatch) -> None:
    submission = _submission()
    reader = SimpleNamespace(
        try_get_message=lambda state: (
            "final",
            {
                "session_id": "ses-1",
                "last_assistant_id": "msg_1",
                "last_assistant_parent_id": "msg_user",
                "last_assistant_req_id": "job_1",
                "last_assistant_completed": 123,
            },
        )
    )
    prepared = SimpleNamespace(reader=reader)

    monkeypatch.setattr(
        "provider_backends.opencode.execution_runtime.polling.prepare_active_poll",
        lambda submission, now: prepared,
    )

    result = poll_submission(
        submission,
        now="2026-04-06T00:00:01Z",
        state_session_path_fn=lambda state: "/tmp/opencode-session",
    )

    assert result is not None
    assert [item.kind for item in result.items] == [
        CompletionItemKind.SESSION_ROTATE,
        CompletionItemKind.ANCHOR_SEEN,
        CompletionItemKind.ASSISTANT_FINAL,
        CompletionItemKind.TURN_BOUNDARY,
    ]
    assert result.submission.reply == "final"


def test_opencode_poll_submission_ignores_mismatched_req_binding(monkeypatch) -> None:
    submission = _submission()
    reader = SimpleNamespace(
        try_get_message=lambda state: (
            "other",
            {
                "session_id": "ses-1",
                "last_assistant_id": "msg_other",
                "last_assistant_parent_id": "msg_user_other",
                "last_assistant_req_id": "job_other",
                "last_assistant_completed": 321,
            },
        )
    )
    prepared = SimpleNamespace(reader=reader)

    monkeypatch.setattr(
        "provider_backends.opencode.execution_runtime.polling.prepare_active_poll",
        lambda submission, now: prepared,
    )

    result = poll_submission(
        submission,
        now="2026-04-06T00:00:01Z",
        state_session_path_fn=lambda state: None,
    )

    assert result is not None
    assert [item.kind for item in result.items] == [CompletionItemKind.ANCHOR_SEEN]
    assert result.submission.reply == ""
    assert result.submission.runtime_state["state"]["last_assistant_req_id"] == "job_other"


def test_opencode_poll_submission_returns_none_without_reply(monkeypatch) -> None:
    submission = _submission()
    reader = SimpleNamespace(try_get_message=lambda state: (None, {}))
    prepared = SimpleNamespace(reader=reader)

    monkeypatch.setattr(
        "provider_backends.opencode.execution_runtime.polling.prepare_active_poll",
        lambda submission, now: prepared,
    )

    result = poll_submission(
        submission,
        now="2026-04-06T00:00:01Z",
        state_session_path_fn=lambda state: None,
    )

    assert result is not None
    assert [item.kind for item in result.items] == [CompletionItemKind.ANCHOR_SEEN]
