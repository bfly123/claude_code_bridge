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
        runtime_root="/tmp/runtime",
    )


def test_persisted_execution_state_round_trips_extended_runtime_context() -> None:
    persisted = PersistedExecutionState(
        submission=_submission(),
        runtime_context=ProviderRuntimeContext(
            agent_name='agent1',
            workspace_path='/tmp/demo',
            backend_type='pane-backed',
            runtime_ref='psmux:%8',
            session_ref='session-8',
            runtime_root='C:/tmp/runtime-agent1',
            runtime_pid=808,
            runtime_health='healthy',
            runtime_binding_source='provider-session',
            terminal_backend='psmux',
            session_file='C:/tmp/agent1.session.json',
            session_id='sid-8',
            tmux_socket_name='psmux-agent1',
            tmux_socket_path=r'\\.\pipe\psmux-agent1',
            job_id='job-object-8',
            job_owner_pid=888,
        ),
        resume_capable=True,
        persisted_at='2026-04-06T00:00:00Z',
    )

    restored = PersistedExecutionState.from_record(persisted.to_record())

    assert restored.runtime_context is not None
    assert restored.runtime_context.runtime_binding_source == 'provider-session'
    assert restored.runtime_context.terminal_backend == 'psmux'
    assert restored.runtime_context.session_file == 'C:/tmp/agent1.session.json'
    assert restored.runtime_context.session_id == 'sid-8'
    assert restored.runtime_context.runtime_root == 'C:/tmp/runtime-agent1'
    assert restored.runtime_context.tmux_socket_name == 'psmux-agent1'
    assert restored.runtime_context.tmux_socket_path == r'\\.\pipe\psmux-agent1'
    assert restored.runtime_context.job_id == 'job-object-8'
    assert restored.runtime_context.job_owner_pid == 888


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
    assert result.runtime_context == persisted.runtime_context


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


def test_restore_submission_merges_live_and_persisted_runtime_context() -> None:
    resumed: list[ProviderRuntimeContext | None] = []
    persisted = PersistedExecutionState(
        submission=_submission(provider='fake'),
        runtime_context=ProviderRuntimeContext(
            agent_name='agent1',
            workspace_path='/tmp/persisted',
            backend_type='pane-backed',
            runtime_ref='psmux:%7',
            session_ref='session-persisted',
            runtime_root='C:/tmp/persisted-runtime',
            runtime_pid=707,
            runtime_health='degraded',
            runtime_binding_source='provider-session',
            terminal_backend='psmux',
            session_file='C:/tmp/persisted.session.json',
            session_id='sid-persisted',
            tmux_socket_name='psmux-persisted',
            tmux_socket_path=r'\\.\pipe\psmux-persisted',
            job_id='job-object-persisted',
            job_owner_pid=777,
        ),
        resume_capable=True,
        persisted_at='2026-04-06T00:00:00Z',
    )
    state_store = SimpleNamespace(load=lambda job_id: persisted, remove=lambda job_id: None, save=lambda state: None)
    service = SimpleNamespace(
        _active={},
        _state_store=state_store,
        _registry={
            'fake': SimpleNamespace(
                resume=lambda job, submission, context, persisted_state, now: resumed.append(context) or submission
            )
        },
        _pending_replays={},
        _runtime_contexts={},
        _clock=lambda: '2026-04-06T00:00:01Z',
    )
    job = SimpleNamespace(job_id='job_1', agent_name='agent1', provider='fake')

    result = restore_submission(
        service,
        job,
        runtime_context=ProviderRuntimeContext(
            agent_name='agent1',
            workspace_path='/tmp/live',
            backend_type='pane-backed',
            runtime_ref='psmux:%9',
            session_ref=None,
            runtime_root='C:/tmp/live-runtime',
            runtime_pid=909,
            runtime_health='healthy',
            runtime_binding_source='external-attach',
        ),
    )

    assert result.status == 'restored'
    assert resumed and resumed[0] is not None
    assert resumed[0].workspace_path == '/tmp/live'
    assert resumed[0].runtime_ref == 'psmux:%9'
    assert resumed[0].session_ref == 'session-persisted'
    assert resumed[0].runtime_root == 'C:/tmp/live-runtime'
    assert resumed[0].runtime_pid == 909
    assert resumed[0].runtime_health == 'healthy'
    assert resumed[0].runtime_binding_source == 'external-attach'
    assert resumed[0].terminal_backend == 'psmux'
    assert resumed[0].session_file == 'C:/tmp/persisted.session.json'
    assert resumed[0].session_id == 'sid-persisted'
    assert resumed[0].tmux_socket_name == 'psmux-persisted'
    assert resumed[0].tmux_socket_path == r'\\.\pipe\psmux-persisted'
    assert resumed[0].job_id == 'job-object-persisted'
    assert resumed[0].job_owner_pid == 777
    assert result.runtime_context == resumed[0]
    assert service._runtime_contexts['job_1'] == resumed[0]
