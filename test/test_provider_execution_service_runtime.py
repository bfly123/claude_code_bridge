from __future__ import annotations

from types import SimpleNamespace

from completion.models import (
    CompletionConfidence,
    CompletionCursor,
    CompletionDecision,
    CompletionItem,
    CompletionItemKind,
    CompletionSourceKind,
    CompletionStatus,
)
from provider_execution.base import ProviderRuntimeContext, ProviderSubmission
from provider_execution.reliability import CompletionReliabilityPolicy
from provider_execution.service_runtime.polling import poll_updates
from provider_execution.service_runtime.restore import restore_submission
from provider_execution.state_models import PersistedExecutionState


def _submission(job_id: str = "job_1", provider: str = "fake") -> ProviderSubmission:
    return ProviderSubmission(
        job_id=job_id,
        agent_name="agent1",
        provider=provider,
        accepted_at="2026-04-06T00:00:00Z",
        ready_at="2026-04-06T00:00:00Z",
        source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM,
        reply="",
    )


def _decision(*, reply: str = "done") -> CompletionDecision:
    return CompletionDecision(
        terminal=True,
        status=CompletionStatus.COMPLETED,
        reason="result_message",
        confidence=CompletionConfidence.EXACT,
        reply=reply,
        anchor_seen=True,
        reply_started=True,
        reply_stable=True,
        provider_turn_ref=None,
        source_cursor=None,
        finished_at="2026-04-06T00:00:01Z",
        diagnostics={},
    )


def _item(seq: int = 1) -> CompletionItem:
    return CompletionItem(
        kind=CompletionItemKind.RESULT,
        timestamp="2026-04-06T00:00:01Z",
        cursor=CompletionCursor(source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM, event_seq=seq),
        provider="fake",
        agent_name="agent1",
        req_id="job_1",
        payload={"text": "done"},
    )


def _runtime_context() -> ProviderRuntimeContext:
    return ProviderRuntimeContext(
        agent_name="agent1",
        workspace_path="/tmp/demo",
        backend_type="pane-backed",
        runtime_ref="ref",
        session_ref="session",
    )


def test_poll_updates_processes_terminal_result_and_cleans_active_state(monkeypatch) -> None:
    submission = _submission()
    result = SimpleNamespace(submission=submission, items=(_item(),), decision=_decision())
    service = SimpleNamespace(
        _clock=lambda: "2026-04-06T00:00:01Z",
        _pending_replays={},
        _active={"job_1": submission},
        _runtime_contexts={"job_1": _runtime_context()},
        _registry={"fake": SimpleNamespace(poll=lambda current, now: result)},
    )
    persisted: list[tuple[str, object, tuple]] = []
    monkeypatch.setattr(
        "provider_execution.service_runtime.polling.persist_submission",
        lambda service, job_id, pending_decision=None, pending_items=(): persisted.append((job_id, pending_decision, pending_items)),
    )

    updates = poll_updates(service)

    assert len(updates) == 1
    assert updates[0].job_id == "job_1"
    assert updates[0].decision is result.decision
    assert service._active == {}
    assert service._runtime_contexts == {}
    assert persisted == [("job_1", result.decision, result.items)]


def test_poll_updates_keeps_terminal_pending_replay_until_acknowledged() -> None:
    decision = _decision()
    service = SimpleNamespace(
        _clock=lambda: "2026-04-06T00:00:01Z",
        _pending_replays={"job_1": ((), decision)},
        _active={},
        _runtime_contexts={},
        _registry={},
    )

    updates = poll_updates(service)

    assert len(updates) == 1
    assert updates[0].job_id == "job_1"
    assert updates[0].decision is decision
    assert "job_1" in service._pending_replays


def test_poll_updates_terminalizes_reliability_timeout(monkeypatch) -> None:
    submission = _submission(provider="codex")
    adapter = SimpleNamespace(
        poll=lambda current, now: None,
        completion_reliability_policy=CompletionReliabilityPolicy(
            provider="codex",
            primary_authority="protocol_log",
            no_terminal_timeout_s=900.0,
        ),
    )
    service = SimpleNamespace(
        _clock=lambda: "2026-04-06T00:15:01Z",
        _pending_replays={},
        _active={"job_1": submission},
        _runtime_contexts={"job_1": _runtime_context()},
        _registry={"codex": adapter},
    )
    captured: dict[str, object] = {}

    def _persist(service, job_id, pending_decision=None, pending_items=()):
        captured["job_id"] = job_id
        captured["decision"] = pending_decision
        captured["items"] = pending_items
        captured["submission"] = service._active.get(job_id)

    monkeypatch.setattr(
        "provider_execution.service_runtime.polling.persist_submission",
        _persist,
    )

    updates = poll_updates(service)

    assert len(updates) == 1
    update = updates[0]
    assert update.job_id == "job_1"
    assert update.items == ()
    assert update.decision is not None
    assert update.decision.status is CompletionStatus.INCOMPLETE
    assert update.decision.reason == "completion_timeout"
    assert update.decision.confidence is CompletionConfidence.DEGRADED
    assert update.decision.diagnostics["completion_primary_authority"] == "protocol_log"
    assert captured["job_id"] == "job_1"
    assert captured["decision"] is update.decision
    assert captured["items"] == ()
    assert captured["submission"].diagnostics["completion_fallback_source"] == "execution_reliability_monitor"
    assert service._active == {}
    assert service._runtime_contexts == {}


def test_restore_submission_returns_terminal_pending_without_resume() -> None:
    persisted = PersistedExecutionState(
        submission=_submission(provider="fake"),
        runtime_context=_runtime_context(),
        resume_capable=True,
        persisted_at="2026-04-06T00:00:00Z",
        pending_decision=_decision(reply="already finished"),
        pending_items=(),
        applied_event_seqs=(),
    )
    state_store = SimpleNamespace(load=lambda job_id: persisted, remove=lambda job_id: None)
    service = SimpleNamespace(
        _active={},
        _state_store=state_store,
        _registry={"fake": SimpleNamespace()},
        _pending_replays={},
        _runtime_contexts={},
        _clock=lambda: "2026-04-06T00:00:01Z",
    )
    job = SimpleNamespace(job_id="job_1", agent_name="agent1", provider="fake")

    result = restore_submission(service, job)

    assert result.status == "terminal_pending"
    assert result.reason == "terminal_decision_recovered"
    assert result.decision is persisted.pending_decision


def test_restore_submission_abandons_when_adapter_missing() -> None:
    removed: list[str] = []
    persisted = PersistedExecutionState(
        submission=_submission(provider="fake"),
        runtime_context=None,
        resume_capable=False,
        persisted_at="2026-04-06T00:00:00Z",
    )
    state_store = SimpleNamespace(load=lambda job_id: persisted, remove=lambda job_id: removed.append(job_id))
    service = SimpleNamespace(
        _active={},
        _state_store=state_store,
        _registry={},
        _pending_replays={},
        _runtime_contexts={},
        _clock=lambda: "2026-04-06T00:00:01Z",
    )
    job = SimpleNamespace(job_id="job_1", agent_name="agent1", provider="fake")

    result = restore_submission(service, job)

    assert result.status == "abandoned"
    assert result.reason == "adapter_missing"
    assert removed == ["job_1"]
