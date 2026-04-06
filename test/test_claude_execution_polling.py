from __future__ import annotations

from types import SimpleNamespace

from completion.models import CompletionSourceKind
from provider_backends.claude.execution_runtime.polling import poll_submission
from provider_execution.base import ProviderPollResult, ProviderSubmission


def _submission() -> ProviderSubmission:
    return ProviderSubmission(
        job_id="job_1",
        agent_name="agent1",
        provider="claude",
        accepted_at="2026-04-06T00:00:00Z",
        ready_at="2026-04-06T00:00:00Z",
        source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
        reply="",
        runtime_state={"state": {}, "mode": "active"},
    )


def test_poll_submission_returns_hook_result_before_pane_liveness(monkeypatch) -> None:
    submission = _submission()
    prepared = SimpleNamespace(reader=object(), backend=object(), pane_id="%1")
    hook_result = ProviderPollResult(submission=submission)
    liveness_calls: list[str] = []

    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.prepare_active_poll_without_liveness",
        lambda submission, now: prepared,
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.poll_exact_hook",
        lambda submission, now: hook_result,
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.ensure_active_pane_alive",
        lambda submission, backend, pane_id, now: liveness_calls.append(pane_id) or None,
    )

    result = poll_submission(None, submission, now="2026-04-06T00:00:01Z")

    assert result is hook_result
    assert liveness_calls == []


def test_poll_submission_processes_events_until_turn_boundary(monkeypatch) -> None:
    submission = _submission()
    prepared = SimpleNamespace(reader=object(), backend=object(), pane_id="%1")
    poll = SimpleNamespace(anchor_seen=True, reached_turn_boundary=False)
    calls: list[tuple[str, object]] = []
    batches = iter(
        [
            (
                [
                    {"role": "user", "text": "hello"},
                    {"role": "assistant", "text": "done"},
                ],
                {"cursor": 1},
            ),
            ([], {"cursor": 2}),
        ]
    )

    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.prepare_active_poll_without_liveness",
        lambda submission, now: prepared,
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.poll_exact_hook",
        lambda submission, now: None,
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.ensure_active_pane_alive",
        lambda submission, backend, pane_id, now: None,
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.build_poll_state",
        lambda submission: poll,
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.read_events",
        lambda reader, state: next(batches),
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.state_session_path",
        lambda state: f"path-{state['cursor']}",
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.apply_session_rotation",
        lambda submission, poll, new_session_path, now: calls.append(("rotate", new_session_path)),
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.handle_user_event",
        lambda submission, poll, text, now: calls.append(("user", text)),
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.handle_assistant_event",
        lambda submission, poll, event, now: calls.append(("assistant", event["text"]))
        or setattr(poll, "reached_turn_boundary", True),
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.handle_system_event",
        lambda submission, poll, event, now, state: None,
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.finalize_poll_result",
        lambda submission, poll, state: {"state": state, "calls": list(calls)},
    )

    result = poll_submission(None, submission, now="2026-04-06T00:00:01Z")

    assert result["state"] == {"cursor": 1}
    assert result["calls"] == [
        ("rotate", "path-1"),
        ("user", "hello"),
        ("assistant", "done"),
    ]


def test_poll_submission_returns_system_terminal_result(monkeypatch) -> None:
    submission = _submission()
    prepared = SimpleNamespace(reader=object(), backend=object(), pane_id="%1")
    poll = SimpleNamespace(anchor_seen=True, reached_turn_boundary=False)
    terminal_result = ProviderPollResult(submission=submission)

    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.prepare_active_poll_without_liveness",
        lambda submission, now: prepared,
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.poll_exact_hook",
        lambda submission, now: None,
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.ensure_active_pane_alive",
        lambda submission, backend, pane_id, now: None,
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.build_poll_state",
        lambda submission: poll,
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.read_events",
        lambda reader, state: ([{"role": "system", "kind": "error"}], {"cursor": 1}),
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.state_session_path",
        lambda state: None,
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.apply_session_rotation",
        lambda submission, poll, new_session_path, now: None,
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.handle_system_event",
        lambda submission, poll, event, now, state: terminal_result,
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.finalize_poll_result",
        lambda submission, poll, state: (_ for _ in ()).throw(AssertionError("finalize should not run")),
    )

    result = poll_submission(None, submission, now="2026-04-06T00:00:01Z")

    assert result is terminal_result
