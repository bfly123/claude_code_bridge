from __future__ import annotations

from types import SimpleNamespace

from ccbd.api_models import DeliveryScope, JobRecord, JobStatus, MessageEnvelope
from completion.models import CompletionConfidence, CompletionSourceKind, CompletionStatus
from provider_execution.active_runtime.resume import resume_active_submission
from provider_execution.base import ProviderRuntimeContext, ProviderSubmission


def _job() -> JobRecord:
    return JobRecord(
        job_id='job_1',
        submission_id='sub_1',
        agent_name='agent1',
        provider='codex',
        request=MessageEnvelope(
            project_id='proj-1',
            to_agent='agent1',
            from_actor='agent2',
            body='hello',
            task_id=None,
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        ),
        status=JobStatus.RUNNING,
        terminal_decision=None,
        cancel_requested_at=None,
        created_at='2026-04-07T00:00:00Z',
        updated_at='2026-04-07T00:00:00Z',
    )


def _submission(*, mode: str = 'active', completion_dir: str | None = None) -> ProviderSubmission:
    runtime_state: dict[str, object] = {'mode': mode}
    if completion_dir is not None:
        runtime_state['completion_dir'] = completion_dir
    return ProviderSubmission(
        job_id='job_1',
        agent_name='agent1',
        provider='codex',
        accepted_at='2026-04-07T00:00:00Z',
        ready_at='2026-04-07T00:00:00Z',
        source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
        reply='reply',
        status=CompletionStatus.INCOMPLETE,
        reason='in_progress',
        confidence=CompletionConfidence.OBSERVED,
        runtime_state=runtime_state,
    )


def _context(tmp_path) -> ProviderRuntimeContext:
    return ProviderRuntimeContext(
        agent_name='agent1',
        workspace_path=str(tmp_path),
        backend_type='tmux',
        runtime_ref=None,
        session_ref=None,
    )


def test_resume_active_submission_requires_active_workspace(tmp_path) -> None:
    resumed = resume_active_submission(
        _job(),
        _submission(),
        context=None,
        load_session_fn=lambda *_args, **_kwargs: None,
        backend_for_session_fn=lambda _data: None,
        reader_factory=lambda _session: object(),
    )

    assert resumed is None


def test_resume_active_submission_skips_passive_runtime_state(tmp_path) -> None:
    resumed = resume_active_submission(
        _job(),
        _submission(mode='passive'),
        context=_context(tmp_path),
        load_session_fn=lambda *_args, **_kwargs: None,
        backend_for_session_fn=lambda _data: None,
        reader_factory=lambda _session: object(),
    )

    assert resumed is None


def test_resume_active_submission_restores_reader_backend_and_completion_dir(tmp_path) -> None:
    configured: list[tuple[object, dict[str, object], ProviderRuntimeContext]] = []
    session = SimpleNamespace(
        data={'provider': 'codex'},
        ensure_pane=lambda: (True, '%9'),
    )

    resumed = resume_active_submission(
        _job(),
        _submission(),
        context=_context(tmp_path),
        load_session_fn=lambda *_args, **_kwargs: session,
        backend_for_session_fn=lambda _data: 'tmux-backend',
        reader_factory=lambda _session: {'reader': 'ok'},
        configure_reader_fn=lambda reader, state, context: configured.append((reader, dict(state), context)),
        completion_dir_fn=lambda _session: '/tmp/completions',
    )

    assert resumed is not None
    assert resumed.runtime_state['pane_id'] == '%9'
    assert resumed.runtime_state['backend'] == 'tmux-backend'
    assert resumed.runtime_state['reader'] == {'reader': 'ok'}
    assert resumed.runtime_state['completion_dir'] == '/tmp/completions'
    assert configured[0][1]['mode'] == 'active'
