from __future__ import annotations

from completion.models import CompletionSourceKind, CompletionStatus
from provider_backends.claude.execution_runtime.hook_results import poll_exact_hook
from provider_execution.base import ProviderSubmission


def _submission() -> ProviderSubmission:
    return ProviderSubmission(
        job_id="job_1",
        agent_name="agent1",
        provider="claude",
        accepted_at="2026-04-06T00:00:00Z",
        ready_at="2026-04-06T00:00:00Z",
        source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
        reply="",
        runtime_state={
            "completion_dir": "/tmp/completion",
            "next_seq": 7,
        },
    )


def test_poll_exact_hook_builds_failed_terminal_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "provider_backends.claude.execution_runtime.hook_results_runtime.load_event",
        lambda completion_dir, request_anchor: {
            "reply": "bad gateway",
            "timestamp": "2026-04-06T00:01:00Z",
            "status": "failed",
            "hook_event_name": "completion.failed",
            "session_id": "claude-turn-1",
        },
    )

    result = poll_exact_hook(_submission(), now="2026-04-06T00:02:00Z")

    assert result is not None
    assert result.submission.reply == "bad gateway"
    assert result.submission.runtime_state["next_seq"] == 8
    assert result.decision is not None
    assert result.decision.status is CompletionStatus.FAILED
    assert result.decision.reason == "hook_stop_failure"
    assert result.items[0].payload["provider_turn_ref"] == "claude-turn-1"
    assert result.items[0].payload["status"] == "failed"
