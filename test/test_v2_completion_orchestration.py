from __future__ import annotations

from collections import deque

from completion.detectors.terminal_text_quiet import TerminalTextQuietDetector
from completion.detectors.protocol_turn import ProtocolTurnDetector
from completion.models import (
    CompletionCursor,
    CompletionItem,
    CompletionItemKind,
    CompletionRequestContext,
    CompletionSourceKind,
    CompletionStatus,
)
from completion.orchestration import CompletionOrchestrator
from completion.selectors.final_message import FinalMessageSelector


class FakeSource:
    def __init__(self, items):
        self._items = deque(items)
        self._baseline = CompletionCursor(source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM, event_seq=0)

    def capture_baseline(self) -> CompletionCursor:
        return self._baseline

    def poll(self, cursor: CompletionCursor, timeout_s: float) -> CompletionItem | None:
        del cursor, timeout_s
        if not self._items:
            return None
        return self._items.popleft()


def _ctx() -> CompletionRequestContext:
    return CompletionRequestContext(
        req_id='req-1',
        agent_name='agent1',
        provider='codex',
        timeout_s=0.01,
        poll_interval_s=0.001,
    )


def _item(kind: CompletionItemKind, seq: int, ts: str, payload: dict | None = None) -> CompletionItem:
    return CompletionItem(
        kind=kind,
        timestamp=ts,
        cursor=CompletionCursor(source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM, event_seq=seq),
        provider='codex',
        agent_name='agent1',
        req_id='req-1',
        payload=payload or {},
    )


def test_orchestrator_selects_reply_for_protocol_turn() -> None:
    source = FakeSource(
        [
            _item(CompletionItemKind.ANCHOR_SEEN, 1, '2026-03-18T00:00:01Z'),
            _item(CompletionItemKind.ASSISTANT_CHUNK, 2, '2026-03-18T00:00:02Z', {'text': 'partial'}),
            _item(CompletionItemKind.TURN_BOUNDARY, 3, '2026-03-18T00:00:03Z', {'reason': 'task_complete'}),
        ]
    )
    orchestrator = CompletionOrchestrator(now_factory=lambda: '2026-03-18T00:00:10Z')

    decision = orchestrator.run(_ctx(), source, ProtocolTurnDetector(), FinalMessageSelector())
    assert decision.terminal is True
    assert decision.status is CompletionStatus.COMPLETED
    assert decision.reply == 'partial'


def test_orchestrator_allows_terminal_quiet_fallback() -> None:
    source = FakeSource([
        _item(CompletionItemKind.ASSISTANT_CHUNK, 1, '2026-03-18T00:00:01Z', {'text': 'quiet path'}),
    ])
    orchestrator = CompletionOrchestrator(now_factory=lambda: '2026-03-18T00:00:10Z')

    decision = orchestrator.run(
        _ctx(),
        source,
        TerminalTextQuietDetector(),
        FinalMessageSelector(),
    )
    assert decision.terminal is True
    assert decision.status is CompletionStatus.COMPLETED
    assert decision.reason == 'terminal_quiet'
    assert decision.reply == 'quiet path'
