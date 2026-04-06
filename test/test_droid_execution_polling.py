from __future__ import annotations

from types import SimpleNamespace

from completion.models import CompletionItemKind, CompletionSourceKind
from provider_backends.droid.execution_runtime.polling import poll_submission
from provider_execution.base import ProviderSubmission


def _submission() -> ProviderSubmission:
    return ProviderSubmission(
        job_id="job_1",
        agent_name="agent1",
        provider="droid",
        accepted_at="2026-04-06T00:00:00Z",
        ready_at="2026-04-06T00:00:00Z",
        source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
        reply="",
        runtime_state={"state": {}, "next_seq": 1},
    )


def test_droid_poll_submission_emits_rotate_anchor_and_final(monkeypatch) -> None:
    submission = _submission()
    reader = SimpleNamespace()
    prepared = SimpleNamespace(reader=reader)
    batches = iter(
        [
            (
                [
                    ("user", "CCB_REQ_ID: job_1\nrun"),
                    ("assistant", "partial"),
                ],
                {"session_path": "/tmp/s1"},
            ),
            (
                [
                    ("assistant", "final\nCCB_DONE: job_1"),
                ],
                {"session_path": "/tmp/s1"},
            ),
        ]
    )
    reader.try_get_events = lambda state: next(batches, ([], {"session_path": "/tmp/s1"}))

    monkeypatch.setattr(
        "provider_backends.droid.execution_runtime.polling_runtime.service.prepare_active_poll",
        lambda submission, now: prepared,
    )

    result = poll_submission(
        submission,
        now="2026-04-06T00:00:01Z",
        state_session_path_fn=lambda state: state.get("session_path"),
        is_done_text_fn=lambda text, req_id: f"CCB_DONE: {req_id}" in text,
        clean_reply_fn=lambda text, req_id: text.replace(f"CCB_DONE: {req_id}", "").strip(),
    )

    assert result is not None
    assert [item.kind for item in result.items] == [
        CompletionItemKind.SESSION_ROTATE,
        CompletionItemKind.ANCHOR_SEEN,
        CompletionItemKind.ASSISTANT_CHUNK,
        CompletionItemKind.ASSISTANT_FINAL,
    ]
    assert result.submission.reply == "partial\nfinal"
    assert result.submission.runtime_state["session_path"] == "/tmp/s1"


def test_droid_poll_submission_returns_none_without_events(monkeypatch) -> None:
    submission = _submission()
    reader = SimpleNamespace(try_get_events=lambda state: ([], {}))
    prepared = SimpleNamespace(reader=reader)

    monkeypatch.setattr(
        "provider_backends.droid.execution_runtime.polling_runtime.service.prepare_active_poll",
        lambda submission, now: prepared,
    )

    result = poll_submission(
        submission,
        now="2026-04-06T00:00:01Z",
        state_session_path_fn=lambda state: None,
        is_done_text_fn=lambda text, req_id: False,
        clean_reply_fn=lambda text, req_id: text,
    )

    assert result is None
