from __future__ import annotations

from completion.models import CompletionSourceKind, CompletionStatus
from provider_backends.gemini.execution_runtime.polling_runtime.hook import poll_exact_hook
from provider_execution.base import ProviderSubmission


def _submission(**runtime_state) -> ProviderSubmission:
    return ProviderSubmission(
        job_id='job_1',
        agent_name='agent1',
        provider='gemini',
        accepted_at='2026-04-06T00:00:00Z',
        ready_at='2026-04-06T00:00:00Z',
        source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
        reply='',
        runtime_state=runtime_state,
    )


def test_gemini_poll_exact_hook_builds_terminal_result(monkeypatch) -> None:
    monkeypatch.setattr(
        'provider_backends.gemini.execution_runtime.polling_runtime.hook_service.load_event',
        lambda completion_dir, request_anchor: {
            'timestamp': '2026-04-06T00:00:03Z',
            'reply': 'done',
            'status': 'completed',
            'session_id': 'ses_1',
            'hook_event_name': 'on_stop',
            'diagnostics': {'note': 'from-hook'},
        },
    )

    result = poll_exact_hook(
        _submission(completion_dir='/tmp/completion', request_anchor='req_1', next_seq=7, anchor_emitted=True),
        now='2026-04-06T00:00:05Z',
    )

    assert result is not None
    assert result.items[0].kind.value == 'assistant_final'
    assert result.items[0].payload['provider_turn_ref'] == 'ses_1'
    assert result.items[0].payload['note'] == 'from-hook'
    assert result.decision is not None
    assert result.decision.status is CompletionStatus.COMPLETED
    assert result.decision.reason == 'hook_after_agent'
    assert result.decision.provider_turn_ref == 'ses_1'
    assert result.submission.runtime_state['next_seq'] == 8


def test_gemini_poll_exact_hook_uses_fallback_error_text_for_failed_event(monkeypatch) -> None:
    monkeypatch.setattr(
        'provider_backends.gemini.execution_runtime.polling_runtime.hook_service.load_event',
        lambda completion_dir, request_anchor: {
            'reply': '',
            'status': 'failed',
            'diagnostics': {'error_message': 'model unavailable'},
        },
    )

    result = poll_exact_hook(
        _submission(completion_dir='/tmp/completion', request_anchor='req_1', next_seq=1),
        now='2026-04-06T00:00:05Z',
    )

    assert result is not None
    assert result.items[0].payload['text'] == 'model unavailable'
    assert result.decision is not None
    assert result.decision.reason == 'api_error'
