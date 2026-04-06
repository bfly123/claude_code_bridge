from __future__ import annotations

from completion.models import CompletionSourceKind, CompletionItemKind
from provider_backends.claude.execution_runtime.state_machine_runtime import ClaudePollState, handle_assistant_event
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
    )


def test_handle_assistant_event_appends_chunk_and_turn_boundary() -> None:
    poll = ClaudePollState(
        request_anchor="job_1",
        next_seq=1,
        anchor_seen=True,
        reply_buffer="",
        raw_buffer="",
        session_path="/tmp/session.jsonl",
        last_assistant_uuid="",
    )

    handle_assistant_event(
        _submission(),
        poll,
        {
            "text": "hello world\nCCB_DONE: job_1",
            "uuid": "assistant-1",
            "stop_reason": "end_turn",
        },
        now="2026-04-06T00:01:00Z",
    )

    assert [item.kind for item in poll.items] == [
        CompletionItemKind.ASSISTANT_CHUNK,
        CompletionItemKind.TURN_BOUNDARY,
    ]
    assert poll.reply_buffer == "hello world"
    assert poll.last_assistant_uuid == "assistant-1"
    assert poll.reached_turn_boundary is True
    assert poll.items[0].payload["assistant_uuid"] == "assistant-1"
    assert poll.items[1].payload["last_agent_message"] == "hello world"


def test_handle_assistant_event_keeps_primary_uuid_for_subagent_chunks() -> None:
    poll = ClaudePollState(
        request_anchor="job_1",
        next_seq=3,
        anchor_seen=True,
        reply_buffer="existing",
        raw_buffer="existing",
        session_path="",
        last_assistant_uuid="primary-uuid",
    )

    handle_assistant_event(
        _submission(),
        poll,
        {
            "text": "subagent update",
            "uuid": "subagent-uuid",
            "subagent_id": "worker-1",
        },
        now="2026-04-06T00:01:00Z",
    )

    assert poll.last_assistant_uuid == "primary-uuid"
    assert poll.items[0].payload["assistant_uuid"] == "subagent-uuid"
    assert poll.items[0].payload["subagent_id"] == "worker-1"
