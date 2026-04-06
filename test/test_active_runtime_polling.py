from __future__ import annotations

from completion.models import CompletionItemKind, CompletionSourceKind, CompletionStatus
from provider_execution.active import ensure_active_pane_alive, prepare_active_poll
from provider_execution.base import ProviderSubmission


def _submission(**runtime_state) -> ProviderSubmission:
    return ProviderSubmission(
        job_id="job_1",
        agent_name="agent1",
        provider="codex",
        accepted_at="2026-04-06T00:00:00Z",
        ready_at="2026-04-06T00:00:00Z",
        source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
        reply="",
        runtime_state=runtime_state,
    )


def test_prepare_active_poll_returns_runtime_error_for_passive_mode() -> None:
    submission = _submission(mode="passive", reason="runtime_unavailable", error="missing_reader")

    result = prepare_active_poll(submission, now="2026-04-06T00:00:01Z")

    assert result is not None
    assert result.items[0].kind is CompletionItemKind.ERROR
    assert result.decision is not None
    assert result.decision.status is CompletionStatus.FAILED
    assert result.decision.reason == "runtime_unavailable"
    assert result.decision.diagnostics["error"] == "missing_reader"


def test_ensure_active_pane_alive_marks_dead_pane(monkeypatch) -> None:
    submission = _submission(mode="active", next_seq=4)

    monkeypatch.setattr(
        "provider_execution.active_runtime.polling_runtime.service.is_runtime_target_alive",
        lambda backend, pane_id: False,
    )

    result = ensure_active_pane_alive(submission, backend=object(), pane_id="%7", now="2026-04-06T00:00:01Z")

    assert result is not None
    assert result.items[0].kind is CompletionItemKind.PANE_DEAD
    assert result.items[0].cursor.event_seq == 4
    assert result.decision is not None
    assert result.decision.status is CompletionStatus.FAILED
    assert result.decision.reason == "pane_dead"
