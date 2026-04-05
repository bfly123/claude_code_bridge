from __future__ import annotations

from completion.models import CompletionItemKind, CompletionStatus

from .models import FakeDirective, TERMINAL_KIND_BY_STATUS


def default_script(directive: FakeDirective, *, mode: str) -> tuple[dict[str, object], ...]:
    latency_ms = max(0, int(directive.latency_seconds * 1000))
    chunk_ms = 0 if latency_ms == 0 else max(1, latency_ms // 2)
    if mode == 'protocol_turn':
        if directive.status is CompletionStatus.COMPLETED:
            return (
                {'t': 0, 'type': CompletionItemKind.ANCHOR_SEEN.value},
                {'t': chunk_ms, 'type': CompletionItemKind.ASSISTANT_CHUNK.value},
                {'t': latency_ms, 'type': CompletionItemKind.TURN_BOUNDARY.value, 'reason': 'task_complete'},
            )
        if directive.status is CompletionStatus.CANCELLED:
            return (
                {'t': 0, 'type': CompletionItemKind.ANCHOR_SEEN.value},
                {'t': latency_ms, 'type': CompletionItemKind.TURN_ABORTED.value, 'reason': directive.reason, 'status': directive.status.value},
            )
        if directive.status is CompletionStatus.FAILED:
            return (
                {'t': 0, 'type': CompletionItemKind.ANCHOR_SEEN.value},
                {'t': latency_ms, 'type': CompletionItemKind.ERROR.value, 'reason': directive.reason},
            )
        return (
            {'t': 0, 'type': CompletionItemKind.ANCHOR_SEEN.value},
            {'t': latency_ms, 'type': CompletionItemKind.TURN_ABORTED.value, 'reason': directive.reason, 'status': directive.status.value},
        )

    if mode == 'session_boundary':
        if directive.status is CompletionStatus.COMPLETED:
            return (
                {'t': chunk_ms, 'type': CompletionItemKind.ASSISTANT_CHUNK.value},
                {'t': latency_ms, 'type': CompletionItemKind.TURN_BOUNDARY.value, 'reason': 'turn_duration'},
            )
        if directive.status is CompletionStatus.CANCELLED:
            return ({'t': latency_ms, 'type': CompletionItemKind.CANCEL_INFO.value, 'reason': directive.reason},)
        return ({'t': latency_ms, 'type': CompletionItemKind.ERROR.value, 'reason': directive.reason},)

    if mode == 'anchored_session_stability':
        if directive.status is CompletionStatus.COMPLETED:
            return (
                {'t': 0, 'type': CompletionItemKind.ANCHOR_SEEN.value},
                {'t': latency_ms, 'type': CompletionItemKind.SESSION_SNAPSHOT.value, 'reply': None},
            )
        if directive.status is CompletionStatus.CANCELLED:
            return (
                {'t': 0, 'type': CompletionItemKind.ANCHOR_SEEN.value},
                {'t': latency_ms, 'type': CompletionItemKind.CANCEL_INFO.value, 'reason': directive.reason},
            )
        if directive.status is CompletionStatus.FAILED:
            return (
                {'t': 0, 'type': CompletionItemKind.ANCHOR_SEEN.value},
                {'t': latency_ms, 'type': CompletionItemKind.ERROR.value, 'reason': directive.reason},
            )
        return (
            {'t': 0, 'type': CompletionItemKind.ANCHOR_SEEN.value},
            {'t': latency_ms, 'type': CompletionItemKind.SESSION_SNAPSHOT.value, 'reply': None},
        )

    if mode == 'legacy_text':
        if directive.status is CompletionStatus.COMPLETED:
            return (
                {'t': latency_ms, 'type': CompletionItemKind.ASSISTANT_FINAL.value, 'done_marker': True},
            )
        if directive.status is CompletionStatus.CANCELLED:
            return ({'t': latency_ms, 'type': CompletionItemKind.CANCEL_INFO.value, 'reason': directive.reason},)
        return ({'t': latency_ms, 'type': CompletionItemKind.ERROR.value, 'reason': directive.reason},)

    terminal_kind = TERMINAL_KIND_BY_STATUS[directive.status]
    terminal_event: dict[str, object] = {'t': latency_ms, 'type': terminal_kind.value}
    if terminal_kind is CompletionItemKind.TURN_ABORTED:
        terminal_event['status'] = directive.status.value
    return (
        {'t': 0, 'type': CompletionItemKind.ANCHOR_SEEN.value},
        {'t': chunk_ms, 'type': CompletionItemKind.ASSISTANT_CHUNK.value},
        terminal_event,
    )


__all__ = ['default_script']
