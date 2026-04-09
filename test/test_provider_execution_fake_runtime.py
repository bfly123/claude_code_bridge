from __future__ import annotations

import pytest

from completion.models import (
    CompletionConfidence,
    CompletionCursor,
    CompletionItemKind,
    CompletionSourceKind,
    CompletionStatus,
)
from provider_execution.base import ProviderSubmission
from provider_execution.fake_runtime import FakeDirective, build_terminal_decision, default_script, materialize_payload
from provider_execution.fake_runtime.parsing import parse_directive


def _submission() -> ProviderSubmission:
    return ProviderSubmission(
        job_id="job_1",
        agent_name="agent1",
        provider="fake",
        accepted_at="2026-04-06T00:00:00Z",
        ready_at="2026-04-06T00:00:00Z",
        source_kind=CompletionSourceKind.STRUCTURED_RESULT_STREAM,
        reply="default reply",
        status=CompletionStatus.COMPLETED,
        reason="result_message",
        confidence=CompletionConfidence.EXACT,
        diagnostics={"origin": "test"},
    )


def test_materialize_payload_merges_chunk_and_sets_terminal_reason() -> None:
    chunk_payload, reply_buffer = materialize_payload(
        CompletionItemKind.ASSISTANT_CHUNK,
        {},
        reply_buffer="hello",
        default_reply="ignored",
        turn_ref="job_1",
        terminal_reason="result_message",
    )
    terminal_payload, final_reply = materialize_payload(
        CompletionItemKind.RESULT,
        {},
        reply_buffer=reply_buffer,
        default_reply="ignored",
        turn_ref="job_1",
        terminal_reason="result_message",
    )

    assert chunk_payload["merged_text"] == "helloignored"
    assert terminal_payload["reply"] == "helloignored"
    assert terminal_payload["reason"] == "result_message"
    assert final_reply == "helloignored"


def test_build_terminal_decision_records_fake_terminal_kind() -> None:
    decision = build_terminal_decision(
        _submission(),
        payload={"kind": "result", "turn_id": "turn_1"},
        cursor=CompletionCursor(
            source_kind=CompletionSourceKind.STRUCTURED_RESULT_STREAM,
            event_seq=3,
            updated_at="2026-04-06T00:00:01Z",
        ),
        finished_at="2026-04-06T00:00:01Z",
        reply="done",
    )

    assert decision.status is CompletionStatus.COMPLETED
    assert decision.provider_turn_ref == "turn_1"
    assert decision.diagnostics["fake_terminal_kind"] == "result"


def test_default_script_protocol_turn_cancelled_uses_aborted_terminal_event() -> None:
    directive = FakeDirective(
        status=CompletionStatus.CANCELLED,
        reason="cancelled_by_test",
        confidence=CompletionConfidence.EXACT,
        latency_seconds=0.2,
        script=(),
    )

    events = default_script(directive, mode="protocol_turn")

    assert [event["type"] for event in events] == [
        CompletionItemKind.ANCHOR_SEEN.value,
        CompletionItemKind.TURN_ABORTED.value,
    ]
    assert events[-1]["reason"] == "cancelled_by_test"
    assert events[-1]["status"] == CompletionStatus.CANCELLED.value


def test_parse_directive_defaults_to_completed_for_plain_task_id() -> None:
    directive = parse_directive('task-1', default_latency_seconds=0.3)

    assert directive.status is CompletionStatus.COMPLETED
    assert directive.reason == 'result_message'
    assert directive.confidence is CompletionConfidence.EXACT
    assert directive.latency_seconds == 0.3
    assert directive.script == ()


def test_parse_directive_reads_latency_reason_and_script() -> None:
    directive = parse_directive(
        'fake;status=failed;confidence=observed;latency_ms=1200;script=[{"type":"result"}]',
        default_latency_seconds=0.1,
    )

    assert directive.status is CompletionStatus.FAILED
    assert directive.reason == 'api_error'
    assert directive.confidence is CompletionConfidence.OBSERVED
    assert directive.latency_seconds == 1.2
    assert directive.script == ({'type': 'result'},)


def test_parse_directive_rejects_invalid_segments() -> None:
    with pytest.raises(ValueError, match='invalid fake task_id directive segment'):
        parse_directive('fake;bad-segment', default_latency_seconds=0.1)
