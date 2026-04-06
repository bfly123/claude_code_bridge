from __future__ import annotations

from completion.models import CompletionItemKind, CompletionStatus

from .models import FakeDirective, TERMINAL_KIND_BY_STATUS


def default_script(directive: FakeDirective, *, mode: str) -> tuple[dict[str, object], ...]:
    latency_ms, chunk_ms = script_timings(directive)
    if mode == "protocol_turn":
        return protocol_turn_script(directive, latency_ms=latency_ms, chunk_ms=chunk_ms)
    if mode == "session_boundary":
        return session_boundary_script(directive, latency_ms=latency_ms, chunk_ms=chunk_ms)
    if mode == "anchored_session_stability":
        return anchored_session_script(directive, latency_ms=latency_ms)
    if mode == "legacy_text":
        return legacy_text_script(directive, latency_ms=latency_ms)
    return default_terminal_script(directive, latency_ms=latency_ms, chunk_ms=chunk_ms)


def script_timings(directive: FakeDirective) -> tuple[int, int]:
    latency_ms = max(0, int(directive.latency_seconds * 1000))
    chunk_ms = 0 if latency_ms == 0 else max(1, latency_ms // 2)
    return latency_ms, chunk_ms


def protocol_turn_script(
    directive: FakeDirective,
    *,
    latency_ms: int,
    chunk_ms: int,
) -> tuple[dict[str, object], ...]:
    if directive.status is CompletionStatus.COMPLETED:
        return (
            event(0, CompletionItemKind.ANCHOR_SEEN),
            event(chunk_ms, CompletionItemKind.ASSISTANT_CHUNK),
            event(latency_ms, CompletionItemKind.TURN_BOUNDARY, reason="task_complete"),
        )
    if directive.status is CompletionStatus.CANCELLED:
        return (
            event(0, CompletionItemKind.ANCHOR_SEEN),
            aborted_event(latency_ms, directive),
        )
    if directive.status is CompletionStatus.FAILED:
        return (
            event(0, CompletionItemKind.ANCHOR_SEEN),
            terminal_reason_event(latency_ms, CompletionItemKind.ERROR, directive),
        )
    return (
        event(0, CompletionItemKind.ANCHOR_SEEN),
        aborted_event(latency_ms, directive),
    )


def session_boundary_script(
    directive: FakeDirective,
    *,
    latency_ms: int,
    chunk_ms: int,
) -> tuple[dict[str, object], ...]:
    if directive.status is CompletionStatus.COMPLETED:
        return (
            event(chunk_ms, CompletionItemKind.ASSISTANT_CHUNK),
            event(latency_ms, CompletionItemKind.TURN_BOUNDARY, reason="turn_duration"),
        )
    if directive.status is CompletionStatus.CANCELLED:
        return (terminal_reason_event(latency_ms, CompletionItemKind.CANCEL_INFO, directive),)
    return (terminal_reason_event(latency_ms, CompletionItemKind.ERROR, directive),)


def anchored_session_script(
    directive: FakeDirective,
    *,
    latency_ms: int,
) -> tuple[dict[str, object], ...]:
    if directive.status is CompletionStatus.COMPLETED:
        return (
            event(0, CompletionItemKind.ANCHOR_SEEN),
            event(latency_ms, CompletionItemKind.SESSION_SNAPSHOT, reply=None),
        )
    if directive.status is CompletionStatus.CANCELLED:
        return (
            event(0, CompletionItemKind.ANCHOR_SEEN),
            terminal_reason_event(latency_ms, CompletionItemKind.CANCEL_INFO, directive),
        )
    if directive.status is CompletionStatus.FAILED:
        return (
            event(0, CompletionItemKind.ANCHOR_SEEN),
            terminal_reason_event(latency_ms, CompletionItemKind.ERROR, directive),
        )
    return (
        event(0, CompletionItemKind.ANCHOR_SEEN),
        event(latency_ms, CompletionItemKind.SESSION_SNAPSHOT, reply=None),
    )


def legacy_text_script(
    directive: FakeDirective,
    *,
    latency_ms: int,
) -> tuple[dict[str, object], ...]:
    if directive.status is CompletionStatus.COMPLETED:
        return (event(latency_ms, CompletionItemKind.ASSISTANT_FINAL, done_marker=True),)
    if directive.status is CompletionStatus.CANCELLED:
        return (terminal_reason_event(latency_ms, CompletionItemKind.CANCEL_INFO, directive),)
    return (terminal_reason_event(latency_ms, CompletionItemKind.ERROR, directive),)


def default_terminal_script(
    directive: FakeDirective,
    *,
    latency_ms: int,
    chunk_ms: int,
) -> tuple[dict[str, object], ...]:
    terminal_kind = TERMINAL_KIND_BY_STATUS[directive.status]
    terminal_event = event(latency_ms, terminal_kind)
    if terminal_kind is CompletionItemKind.TURN_ABORTED:
        terminal_event["status"] = directive.status.value
    return (
        event(0, CompletionItemKind.ANCHOR_SEEN),
        event(chunk_ms, CompletionItemKind.ASSISTANT_CHUNK),
        terminal_event,
    )


def aborted_event(latency_ms: int, directive: FakeDirective) -> dict[str, object]:
    return event(
        latency_ms,
        CompletionItemKind.TURN_ABORTED,
        reason=directive.reason,
        status=directive.status.value,
    )


def terminal_reason_event(
    latency_ms: int,
    kind: CompletionItemKind,
    directive: FakeDirective,
) -> dict[str, object]:
    return event(latency_ms, kind, reason=directive.reason)


def event(timestamp_ms: int, kind: CompletionItemKind, **payload: object) -> dict[str, object]:
    return {"t": timestamp_ms, "type": kind.value, **payload}


__all__ = ["default_script"]
