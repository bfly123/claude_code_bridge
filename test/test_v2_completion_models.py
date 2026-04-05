from __future__ import annotations

import pytest

from agents.models import AgentSpec, PermissionMode, QueuePolicy, RestoreMode, RuntimeMode, WorkspaceMode
from completion.models import (
    CompletionConfidence,
    CompletionCursor,
    CompletionDecision,
    CompletionFamily,
    CompletionItem,
    CompletionItemKind,
    CompletionProfile,
    CompletionRequestContext,
    CompletionSourceKind,
    CompletionStatus,
    ReplyCandidateKind,
    SelectorFamily,
    reply_candidates_from_item,
)
from completion.profiles import CompletionManifest, build_completion_profile


BASE_CURSOR = CompletionCursor(source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM, event_seq=0)


def test_completion_decision_pending_validation() -> None:
    pending = CompletionDecision.pending(cursor=BASE_CURSOR)
    assert pending.terminal is False
    assert pending.status is CompletionStatus.INCOMPLETE
    assert pending.source_cursor == BASE_CURSOR


def test_terminal_decision_requires_reason_confidence_and_finished_at() -> None:
    with pytest.raises(ValueError):
        CompletionDecision(
            terminal=True,
            status=CompletionStatus.COMPLETED,
            reason=None,
            confidence=CompletionConfidence.EXACT,
            reply='',
            anchor_seen=False,
            reply_started=False,
            reply_stable=False,
            provider_turn_ref=None,
            source_cursor=BASE_CURSOR,
            finished_at='2026-03-18T00:00:00Z',
            diagnostics={},
        )


def test_reply_candidates_are_extracted_in_priority_bands() -> None:
    item = CompletionItem(
        kind=CompletionItemKind.RESULT,
        timestamp='2026-03-18T00:00:05Z',
        cursor=BASE_CURSOR,
        provider='codex',
        agent_name='Agent1',
        req_id='req-1',
        payload={'last_agent_message': 'final agent', 'result_text': 'result reply'},
    )

    candidates = reply_candidates_from_item(item)
    assert [candidate.kind for candidate in candidates] == [
        ReplyCandidateKind.LAST_AGENT_MESSAGE,
        ReplyCandidateKind.FINAL_ANSWER,
    ]


def test_build_completion_profile_from_manifest() -> None:
    spec = AgentSpec(
        name='agent1',
        provider='codex',
        target='.',
        workspace_mode=WorkspaceMode.GIT_WORKTREE,
        workspace_root=None,
        runtime_mode=RuntimeMode.PANE_BACKED,
        restore_default=RestoreMode.AUTO,
        permission_default=PermissionMode.MANUAL,
        queue_policy=QueuePolicy.SERIAL_PER_AGENT,
    )
    manifest = CompletionManifest(
        provider='codex',
        runtime_mode='pane-backed',
        completion_family=CompletionFamily.PROTOCOL_TURN,
        completion_source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM,
        supports_exact_completion=True,
        supports_observed_completion=False,
        supports_anchor_binding=True,
        supports_reply_stability=False,
        supports_terminal_reason=True,
        selector_family=SelectorFamily.FINAL_MESSAGE,
    )

    profile = build_completion_profile(spec, manifest)
    assert isinstance(profile, CompletionProfile)
    assert profile.completion_family is CompletionFamily.PROTOCOL_TURN
    assert profile.runtime_mode is RuntimeMode.PANE_BACKED

def test_request_context_normalizes_agent_name() -> None:
    context = CompletionRequestContext(
        req_id='req-1',
        agent_name='Agent1',
        provider='gemini',
        timeout_s=5,
        anchor_text='anchor',
    )
    assert context.agent_name == 'agent1'
