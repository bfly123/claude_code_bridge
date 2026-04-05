from __future__ import annotations

from dataclasses import dataclass

from completion.models import CompletionConfidence, CompletionItemKind, CompletionStatus

DEFAULT_LATENCY_SECONDS = 0.2
TERMINAL_KIND_BY_STATUS = {
    CompletionStatus.COMPLETED: CompletionItemKind.RESULT,
    CompletionStatus.CANCELLED: CompletionItemKind.CANCEL_INFO,
    CompletionStatus.FAILED: CompletionItemKind.ERROR,
    CompletionStatus.INCOMPLETE: CompletionItemKind.TURN_ABORTED,
}
EVENT_KIND_BY_NAME = {
    'anchor_seen': CompletionItemKind.ANCHOR_SEEN,
    'assistant_chunk': CompletionItemKind.ASSISTANT_CHUNK,
    'assistant_final': CompletionItemKind.ASSISTANT_FINAL,
    'tool_call': CompletionItemKind.TOOL_CALL,
    'tool_result': CompletionItemKind.TOOL_RESULT,
    'result': CompletionItemKind.RESULT,
    'turn_boundary': CompletionItemKind.TURN_BOUNDARY,
    'turn_aborted': CompletionItemKind.TURN_ABORTED,
    'cancel_info': CompletionItemKind.CANCEL_INFO,
    'error': CompletionItemKind.ERROR,
    'pane_dead': CompletionItemKind.PANE_DEAD,
    'session_snapshot': CompletionItemKind.SESSION_SNAPSHOT,
    'session_mutation': CompletionItemKind.SESSION_MUTATION,
    'session_rotate': CompletionItemKind.SESSION_ROTATE,
    'sleep': None,
}
TERMINAL_KINDS = {
    CompletionItemKind.RESULT,
    CompletionItemKind.TURN_BOUNDARY,
    CompletionItemKind.TURN_ABORTED,
    CompletionItemKind.CANCEL_INFO,
    CompletionItemKind.ERROR,
    CompletionItemKind.PANE_DEAD,
}


@dataclass(frozen=True)
class FakeDirective:
    status: CompletionStatus
    reason: str
    confidence: CompletionConfidence
    latency_seconds: float
    script: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class FakeScriptEvent:
    at_ms: int
    kind: CompletionItemKind | None
    payload: dict[str, object]


__all__ = [
    'DEFAULT_LATENCY_SECONDS',
    'EVENT_KIND_BY_NAME',
    'FakeDirective',
    'FakeScriptEvent',
    'TERMINAL_KINDS',
    'TERMINAL_KIND_BY_STATUS',
]
