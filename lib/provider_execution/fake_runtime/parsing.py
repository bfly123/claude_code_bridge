from __future__ import annotations

import json

from completion.models import CompletionConfidence, CompletionStatus

from .models import EVENT_KIND_BY_NAME, FakeDirective, FakeScriptEvent


def normalize_script_event(raw: dict[str, object]) -> FakeScriptEvent:
    if not isinstance(raw, dict):
        raise ValueError('fake script events must be objects')
    event_type = str(raw.get('type') or '').strip().lower()
    if not event_type:
        raise ValueError('fake script events require type')
    try:
        kind = EVENT_KIND_BY_NAME[event_type]
    except KeyError as exc:
        raise ValueError(f'unsupported fake script event type: {event_type!r}') from exc
    at_ms = int(raw.get('t', 0))
    if at_ms < 0:
        raise ValueError('fake script event t must be >= 0')
    payload = {str(key): value for key, value in raw.items() if key not in {'t', 'type'}}
    return FakeScriptEvent(at_ms=at_ms, kind=kind, payload=payload)


def parse_directive(task_id: str | None, *, default_latency_seconds: float) -> FakeDirective:
    if task_id is None or not task_id.startswith('fake;'):
        return FakeDirective(
            status=CompletionStatus.COMPLETED,
            reason='result_message',
            confidence=CompletionConfidence.EXACT,
            latency_seconds=default_latency_seconds,
            script=(),
        )

    options: dict[str, str] = {}
    for part in task_id.split(';')[1:]:
        item = part.strip()
        if not item:
            continue
        if '=' not in item:
            raise ValueError(f'invalid fake task_id directive segment: {item!r}')
        key, value = item.split('=', 1)
        options[key.strip().lower()] = value.strip()

    status = CompletionStatus(options.get('status', CompletionStatus.COMPLETED.value))
    confidence = CompletionConfidence(options.get('confidence', CompletionConfidence.EXACT.value))
    default_reason_by_status = {
        CompletionStatus.COMPLETED: 'result_message',
        CompletionStatus.CANCELLED: 'cancel_info',
        CompletionStatus.FAILED: 'api_error',
        CompletionStatus.INCOMPLETE: 'timeout',
    }
    reason = options.get('reason', default_reason_by_status[status])
    latency_ms_raw = options.get('latency_ms')
    latency_seconds = default_latency_seconds
    if latency_ms_raw is not None:
        latency_seconds = max(0.0, int(latency_ms_raw) / 1000.0)

    script: tuple[dict[str, object], ...] = ()
    script_raw = options.get('script')
    if script_raw is not None:
        try:
            parsed = json.loads(script_raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f'invalid fake script JSON: {exc}') from exc
        if not isinstance(parsed, list):
            raise ValueError('fake script must be a JSON list')
        script = tuple(dict(item) for item in parsed)

    return FakeDirective(
        status=status,
        reason=reason,
        confidence=confidence,
        latency_seconds=latency_seconds,
        script=script,
    )


__all__ = ['normalize_script_event', 'parse_directive']
