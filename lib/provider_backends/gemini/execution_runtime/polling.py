from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from completion.models import (
    CompletionConfidence,
    CompletionCursor,
    CompletionDecision,
    CompletionItemKind,
    CompletionStatus,
)
from provider_execution.active import ensure_active_pane_alive, prepare_active_poll_without_liveness
from provider_execution.base import ProviderPollResult, ProviderSubmission
from provider_execution.common import build_item, request_anchor_from_runtime_state
from provider_hooks.artifacts import load_event

from .start import state_session_path


def poll_submission(submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
    prepared = prepare_active_poll_without_liveness(submission, now=now)
    if prepared is None or isinstance(prepared, ProviderPollResult):
        return prepared

    hook_result = poll_exact_hook(submission, now=now)
    if hook_result is not None:
        return hook_result

    pane_dead_result = ensure_active_pane_alive(submission, backend=prepared.backend, pane_id=prepared.pane_id, now=now)
    if pane_dead_result is not None:
        return pane_dead_result

    state = submission.runtime_state.get('state') or {}
    request_anchor = request_anchor_from_runtime_state(submission.runtime_state, fallback=submission.job_id)
    next_seq = int(submission.runtime_state.get('next_seq', 1))
    anchor_emitted = bool(submission.runtime_state.get('anchor_emitted', False))
    reply_buffer = str(submission.runtime_state.get('reply_buffer') or '')
    session_path = str(submission.runtime_state.get('session_path') or '')
    items = []

    reply, state = prepared.reader.try_get_message(state)
    new_session_path = state_session_path(state)
    if new_session_path and new_session_path != session_path:
        items.append(
            build_item(
                submission,
                kind=CompletionItemKind.SESSION_ROTATE,
                timestamp=now,
                seq=next_seq,
                payload={'session_path': new_session_path, 'provider_session_id': Path(new_session_path).stem},
                cursor_kwargs={'session_path': new_session_path},
            )
        )
        next_seq += 1
        session_path = new_session_path
        reply_buffer = ''
        anchor_emitted = False
    elif new_session_path:
        session_path = new_session_path

    if not anchor_emitted:
        items.append(
            build_item(
                submission,
                kind=CompletionItemKind.ANCHOR_SEEN,
                timestamp=now,
                seq=next_seq,
                payload={'turn_id': request_anchor, 'session_path': session_path or None},
                cursor_kwargs={'session_path': session_path or None},
            )
        )
        next_seq += 1
        anchor_emitted = True

    if reply:
        cleaned = clean_reply(str(reply), req_id=request_anchor)
        if cleaned:
            reply_buffer = cleaned
            items.append(
                build_item(
                    submission,
                    kind=CompletionItemKind.SESSION_SNAPSHOT,
                    timestamp=now,
                    seq=next_seq,
                    payload={
                        'reply': cleaned,
                        'text': cleaned,
                        'content': cleaned,
                        'turn_id': request_anchor,
                        'session_path': session_path or None,
                        'message_count': state.get('msg_count'),
                        'message_id': state.get('last_gemini_id'),
                        'last_updated': state.get('mtime_ns') or state.get('mtime'),
                        'done_marker_seen': bool(request_anchor and is_done_text_fn(str(reply), request_anchor)),
                    },
                    cursor_kwargs={
                        'session_path': session_path or None,
                        'offset': int_or_none(state.get('msg_count')),
                    },
                )
            )
            next_seq += 1

    updated = replace(
        submission,
        reply=reply_buffer,
        runtime_state={
            **submission.runtime_state,
            'state': state,
            'next_seq': next_seq,
            'anchor_emitted': anchor_emitted,
            'reply_buffer': reply_buffer,
            'session_path': session_path,
        },
    )
    if not items:
        return None
    return ProviderPollResult(submission=updated, items=tuple(items))


def clean_reply(reply: str, *, req_id: str) -> str:
    if req_id and is_done_text_fn(reply, req_id):
        extracted = extract_reply_for_req_fn(reply, req_id)
        if extracted.strip():
            return extracted.strip()
    cleaned = strip_done_text_fn(reply, req_id) if req_id else reply
    return cleaned.strip() if cleaned else ''


def int_or_none(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _hook_event_diagnostics(event: dict[str, object]) -> dict[str, object]:
    diagnostics = dict(event.get('diagnostics') or {})
    diagnostics.setdefault('completion_source', 'hook_artifact')
    hook_event_name = event.get('hook_event_name')
    if hook_event_name is not None:
        diagnostics.setdefault('hook_event_name', hook_event_name)
    return diagnostics


def _hook_decision_reason(status: CompletionStatus, diagnostics: dict[str, object]) -> str:
    explicit_reason = str(diagnostics.get('reason') or '').strip().lower()
    if explicit_reason:
        return explicit_reason
    if status is CompletionStatus.FAILED:
        if any(
            str(diagnostics.get(key) or '').strip()
            for key in ('error_type', 'error_code', 'error_message', 'error', 'message', 'text')
        ):
            return 'api_error'
        return 'hook_after_agent_failure'
    if status is CompletionStatus.CANCELLED:
        return 'hook_after_agent_cancelled'
    if status is CompletionStatus.INCOMPLETE:
        return 'hook_after_agent_incomplete'
    return 'hook_after_agent'


def _hook_item_payload(
    *,
    req_id: str,
    reply: str,
    status: CompletionStatus,
    provider_turn_ref: str,
    hook_event_name: object,
    diagnostics: dict[str, object],
) -> dict[str, object]:
    payload: dict[str, object] = {
        'reply': reply,
        'text': reply,
        'turn_id': req_id,
        'provider_turn_ref': provider_turn_ref,
        'completion_source': 'hook_artifact',
        'hook_event_name': hook_event_name,
        'status': status.value,
    }
    if not payload['text']:
        fallback_text = str(
            diagnostics.get('text')
            or diagnostics.get('error_message')
            or diagnostics.get('message')
            or diagnostics.get('error')
            or ''
        ).strip()
        if fallback_text:
            payload['text'] = fallback_text
    for key, value in diagnostics.items():
        if value is None or key in payload:
            continue
        payload[key] = value
    return payload


def poll_exact_hook(submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
    completion_dir = str(submission.runtime_state.get('completion_dir') or '').strip()
    request_anchor = request_anchor_from_runtime_state(submission.runtime_state, fallback=submission.job_id)
    next_seq = int(submission.runtime_state.get('next_seq', 1))
    if not completion_dir or not request_anchor:
        return None
    event = load_event(completion_dir, request_anchor)
    if not event:
        return None
    reply = str(event.get('reply') or '').strip()
    cursor_path = str(Path(completion_dir) / 'events' / f'{request_anchor}.json')
    status = CompletionStatus(str(event.get('status') or CompletionStatus.COMPLETED.value))
    diagnostics = _hook_event_diagnostics(event)
    provider_turn_ref = str(event.get('session_id') or request_anchor)
    item = build_item(
        submission,
        kind=CompletionItemKind.ASSISTANT_FINAL,
        timestamp=str(event.get('timestamp') or now),
        seq=next_seq,
        payload=_hook_item_payload(
            req_id=request_anchor,
            reply=reply,
            status=status,
            provider_turn_ref=provider_turn_ref,
            hook_event_name=event.get('hook_event_name'),
            diagnostics=diagnostics,
        ),
        cursor_kwargs={'opaque_cursor': cursor_path},
    )
    decision = CompletionDecision(
        terminal=True,
        status=status,
        reason=_hook_decision_reason(status, diagnostics),
        confidence=CompletionConfidence.EXACT,
        reply=reply,
        anchor_seen=bool(submission.runtime_state.get('anchor_emitted', False)),
        reply_started=bool(reply),
        reply_stable=bool(reply),
        provider_turn_ref=provider_turn_ref,
        source_cursor=CompletionCursor(
            source_kind=submission.source_kind,
            opaque_cursor=cursor_path,
            event_seq=next_seq,
            updated_at=str(event.get('timestamp') or now),
        ),
        finished_at=str(event.get('timestamp') or now),
        diagnostics=diagnostics,
    )
    updated = replace(
        submission,
        reply=reply,
        runtime_state={**submission.runtime_state, 'next_seq': next_seq + 1},
    )
    return ProviderPollResult(submission=updated, items=(item,), decision=decision)


extract_reply_for_req_fn = None
is_done_text_fn = None
strip_done_text_fn = None


__all__ = [
    'clean_reply',
    'int_or_none',
    'poll_exact_hook',
    'poll_submission',
]
