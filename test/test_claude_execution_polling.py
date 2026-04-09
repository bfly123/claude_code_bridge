from __future__ import annotations

from types import SimpleNamespace

from completion.models import CompletionSourceKind
from provider_backends.claude.execution import ClaudeProviderAdapter
from provider_backends.claude.execution_runtime.polling import poll_submission
from provider_backends.claude.execution_runtime.start import looks_ready
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


def test_poll_submission_reply_delivery_waits_for_ready_prompt(monkeypatch) -> None:
    submission = ProviderSubmission(
        job_id="job_reply",
        agent_name="agent1",
        provider="claude",
        accepted_at="2026-04-06T00:00:00Z",
        ready_at="2026-04-06T00:00:00Z",
        source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
        reply="",
        runtime_state={
            "state": {},
            "mode": "active",
            "pane_id": "%1",
            "prompt_text": "CCB_REPLY from=agent2 reply=rep_1",
            "prompt_sent": False,
            "reply_delivery_complete_on_dispatch": True,
            "reply_delivery_require_ready": True,
            "request_anchor": "job_reply",
            "ready_wait_started_at": "2026-04-06T00:00:00Z",
            "ready_timeout_s": 0.0,
        },
    )
    sent: list[tuple[str, str]] = []

    class BusyBackend:
        def get_pane_content(self, pane_id: str, lines: int = 120) -> str:
            assert pane_id == "%1"
            assert lines == 120
            return "Claude is still busy"

        def send_text(self, pane_id: str, text: str) -> None:
            sent.append((pane_id, text))

    prepared = SimpleNamespace(reader=object(), backend=BusyBackend(), pane_id="%1")

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
        lambda submission: SimpleNamespace(
            anchor_seen=False,
            reached_turn_boundary=False,
            items=[],
            next_seq=1,
            request_anchor="job_reply",
            reply_buffer="",
            raw_buffer="",
            session_path="",
            last_assistant_uuid="",
        ),
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.read_events",
        lambda reader, state: ([], state),
    )

    result = poll_submission(None, submission, now="2026-04-06T00:00:01Z")

    assert isinstance(result, ProviderPollResult)
    assert result.decision is None
    assert result.submission.runtime_state["prompt_sent"] is False
    assert sent == []


def test_poll_submission_reply_delivery_completes_after_dispatch(monkeypatch) -> None:
    submission = ProviderSubmission(
        job_id="job_reply",
        agent_name="agent1",
        provider="claude",
        accepted_at="2026-04-06T00:00:00Z",
        ready_at="2026-04-06T00:00:00Z",
        source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
        reply="",
        runtime_state={
            "state": {},
            "mode": "active",
            "pane_id": "%1",
            "prompt_text": "CCB_REPLY from=agent2 reply=rep_1",
            "prompt_sent": False,
            "reply_delivery_complete_on_dispatch": True,
            "reply_delivery_require_ready": True,
            "request_anchor": "job_reply",
            "ready_wait_started_at": "2026-04-06T00:00:00Z",
            "ready_timeout_s": 30.0,
        },
    )
    sent: list[tuple[str, str]] = []

    class ReadyBackend:
        def get_pane_content(self, pane_id: str, lines: int = 120) -> str:
            assert pane_id == "%1"
            assert lines == 120
            return "❯\n  ? for shortcuts"

        def send_text(self, pane_id: str, text: str) -> None:
            sent.append((pane_id, text))

    prepared = SimpleNamespace(reader=object(), backend=ReadyBackend(), pane_id="%1")

    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.prepare_active_poll_without_liveness",
        lambda submission, now: prepared,
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.poll_exact_hook",
        lambda submission, now: (_ for _ in ()).throw(AssertionError("hook should not run")),
    )
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.polling.ensure_active_pane_alive",
        lambda submission, backend, pane_id, now: (_ for _ in ()).throw(AssertionError("liveness should not run")),
    )

    result = poll_submission(None, submission, now="2026-04-06T00:00:01Z")

    assert isinstance(result, ProviderPollResult)
    assert result.decision is not None
    assert result.decision.reason == "reply_delivery_sent"
    assert result.submission.runtime_state["prompt_sent"] is True
    assert sent == [("%1", "CCB_REPLY from=agent2 reply=rep_1")]


def test_looks_ready_accepts_nbsp_prompt_line() -> None:
    text = (
        "────────────────────────────────────────────────────\n"
        "❯\xa0\n"
        "────────────────────────────────────────────────────\n"
        "  ⏵⏵ bypass permissions on (shift+tab to cycle)\n"
    )

    assert looks_ready(text) is True


def test_looks_ready_prefers_prompt_line_over_welcome_banner() -> None:
    text = (
        "Welcome back!\n"
        "Some older banner text\n"
        "────────────────────────────────────────────────────\n"
        "❯\xa0\n"
        "────────────────────────────────────────────────────\n"
        "  ⏵⏵ bypass permissions on (shift+tab to cycle)\n"
    )

    assert looks_ready(text) is True


def test_claude_export_runtime_state_preserves_reply_delivery_flags() -> None:
    adapter = ClaudeProviderAdapter()
    submission = ProviderSubmission(
        job_id="job_reply",
        agent_name="agent1",
        provider="claude",
        accepted_at="2026-04-06T00:00:00Z",
        ready_at="2026-04-06T00:00:00Z",
        source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
        reply="",
        runtime_state={
            "mode": "active",
            "state": {},
            "pane_id": "%1",
            "request_anchor": "job_reply",
            "next_seq": 1,
            "anchor_seen": True,
            "no_wrap": True,
            "reply_buffer": "",
            "raw_buffer": "",
            "session_path": "/tmp/session.jsonl",
            "last_assistant_uuid": "",
            "completion_dir": "/tmp/completion",
            "prompt_text": "CCB_REPLY from=agent2 reply=rep_1",
            "prompt_sent": False,
            "prompt_sent_at": None,
            "reply_delivery_complete_on_dispatch": True,
            "reply_delivery_require_ready": True,
            "ready_wait_started_at": "2026-04-06T00:00:00Z",
            "ready_timeout_s": 8.0,
        },
    )

    exported = adapter.export_runtime_state(submission)

    assert exported["reply_delivery_complete_on_dispatch"] is True
    assert exported["reply_delivery_require_ready"] is True
