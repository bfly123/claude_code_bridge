from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ccbd.system import parse_utc_timestamp
from completion.models import CompletionItemKind
from provider_execution.active import ensure_active_pane_alive, prepare_active_poll_without_liveness
from provider_execution.base import ProviderPollResult, ProviderSubmission
from provider_execution.common import build_item, request_anchor_from_runtime_state

from ..start import looks_ready, send_prompt, state_session_path
from .hook import poll_exact_hook
from .reply import clean_reply, int_or_none


def poll_submission(
    submission,
    *,
    now: str,
    extract_reply_for_req_fn,
    is_done_text_fn,
    strip_done_text_fn,
) -> ProviderPollResult | None:
    prepared = prepare_active_poll_without_liveness(submission, now=now)
    if prepared is None or isinstance(prepared, ProviderPollResult):
        return prepared
    submission, runtime_dirty = _dispatch_deferred_prompt(
        submission,
        backend=prepared.backend,
        pane_id=prepared.pane_id,
        now=now,
    )
    if not bool(submission.runtime_state.get('prompt_sent', True)):
        pane_dead_result = ensure_active_pane_alive(submission, backend=prepared.backend, pane_id=prepared.pane_id, now=now)
        if pane_dead_result is not None:
            return pane_dead_result
        if runtime_dirty:
            return ProviderPollResult(submission=submission)
        return None
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
    session_items, next_seq, session_path, reply_buffer, anchor_emitted = build_session_items(
        submission,
        now=now,
        next_seq=next_seq,
        request_anchor=request_anchor,
        reply=reply,
        state=state,
        session_path=session_path,
        reply_buffer=reply_buffer,
        anchor_emitted=anchor_emitted,
        extract_reply_for_req_fn=extract_reply_for_req_fn,
        is_done_text_fn=is_done_text_fn,
        strip_done_text_fn=strip_done_text_fn,
        new_session_path=new_session_path,
    )
    items.extend(session_items)

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
    runtime_dirty = runtime_dirty or updated.reply != submission.reply or updated.runtime_state != submission.runtime_state
    if not items and not runtime_dirty:
        return None
    return ProviderPollResult(submission=updated, items=tuple(items))


def _dispatch_deferred_prompt(
    submission: ProviderSubmission,
    *,
    backend: object,
    pane_id: str,
    now: str,
) -> tuple[ProviderSubmission, bool]:
    if bool(submission.runtime_state.get('prompt_sent', True)):
        return submission, False
    updated, immediate_due = _observe_prompt_readiness(submission, backend=backend, pane_id=pane_id, now=now)
    runtime_dirty = updated != submission
    if not immediate_due and not _prompt_delivery_due(updated, now=now):
        return updated, runtime_dirty
    prompt = str(updated.runtime_state.get('prompt_text') or '')
    send_prompt(backend, pane_id, prompt)
    sent = replace(
        updated,
        runtime_state={
            **updated.runtime_state,
            'prompt_sent': True,
            'prompt_sent_at': now,
        },
    )
    return sent, True


def _observe_prompt_readiness(
    submission: ProviderSubmission,
    *,
    backend: object,
    pane_id: str,
    now: str,
) -> tuple[ProviderSubmission, bool]:
    get_pane_content = getattr(backend, 'get_pane_content', None)
    if not callable(get_pane_content):
        return submission, True
    try:
        text = str(get_pane_content(pane_id, lines=120) or '')
    except Exception:
        return submission, True

    current_fingerprint = str(submission.runtime_state.get('ready_prompt_fingerprint') or '')
    current_seen_at = str(submission.runtime_state.get('ready_prompt_seen_at') or '')
    if looks_ready(text):
        fingerprint = text.strip()
        if fingerprint != current_fingerprint or not current_seen_at:
            return _with_ready_prompt_state(submission, fingerprint=fingerprint, seen_at=now), False
        return submission, False
    if current_fingerprint or current_seen_at:
        return _with_ready_prompt_state(submission, fingerprint='', seen_at=''), False
    return submission, False


def _with_ready_prompt_state(
    submission: ProviderSubmission,
    *,
    fingerprint: str,
    seen_at: str,
) -> ProviderSubmission:
    return replace(
        submission,
        runtime_state={
            **submission.runtime_state,
            'ready_prompt_fingerprint': fingerprint,
            'ready_prompt_seen_at': seen_at,
        },
    )


def _prompt_delivery_due(submission: ProviderSubmission, *, now: str) -> bool:
    fingerprint = str(submission.runtime_state.get('ready_prompt_fingerprint') or '').strip()
    if fingerprint and _ready_prompt_settled(submission, now=now):
        return True
    return _ready_wait_timed_out(submission, now=now)


def _ready_prompt_settled(submission: ProviderSubmission, *, now: str, settle_s: float = 1.5) -> bool:
    seen_at = str(submission.runtime_state.get('ready_prompt_seen_at') or '').strip()
    if not seen_at:
        return False
    try:
        elapsed = (parse_utc_timestamp(now) - parse_utc_timestamp(seen_at)).total_seconds()
    except Exception:
        return False
    return elapsed >= max(0.0, settle_s)


def _ready_wait_timed_out(submission: ProviderSubmission, *, now: str) -> bool:
    started_at = str(submission.runtime_state.get('ready_wait_started_at') or '').strip()
    if not started_at:
        return True
    try:
        timeout_s = float(submission.runtime_state.get('ready_timeout_s', 20.0))
    except Exception:
        timeout_s = 20.0
    try:
        elapsed = (parse_utc_timestamp(now) - parse_utc_timestamp(started_at)).total_seconds()
    except Exception:
        return True
    return elapsed >= max(0.0, timeout_s)


def build_session_items(
    submission,
    *,
    now: str,
    next_seq: int,
    request_anchor: str,
    reply,
    state: dict,
    session_path: str,
    reply_buffer: str,
    anchor_emitted: bool,
    extract_reply_for_req_fn,
    is_done_text_fn,
    strip_done_text_fn,
    new_session_path: str | None,
):
    items = []
    no_wrap = bool(submission.runtime_state.get('no_wrap', False))
    if new_session_path and new_session_path != session_path:
        items.append(build_session_rotate_item(submission, now=now, next_seq=next_seq, session_path=new_session_path))
        next_seq += 1
        session_path = new_session_path
        reply_buffer = ''
        anchor_emitted = no_wrap
    elif new_session_path:
        session_path = new_session_path

    if not anchor_emitted:
        items.append(build_anchor_item(submission, now=now, next_seq=next_seq, request_anchor=request_anchor, session_path=session_path))
        next_seq += 1
        anchor_emitted = True

    if reply:
        cleaned = clean_reply(
            str(reply),
            req_id=request_anchor,
            extract_reply_for_req_fn=extract_reply_for_req_fn,
            is_done_text_fn=is_done_text_fn,
            strip_done_text_fn=strip_done_text_fn,
        )
        if cleaned:
            reply_buffer = cleaned
            items.append(
                build_snapshot_item(
                    submission,
                    now=now,
                    next_seq=next_seq,
                    request_anchor=request_anchor,
                    session_path=session_path,
                    state=state,
                    reply=reply,
                    cleaned=cleaned,
                    is_done_text_fn=is_done_text_fn,
                )
            )
            next_seq += 1
    return items, next_seq, session_path, reply_buffer, anchor_emitted


def build_session_rotate_item(submission, *, now: str, next_seq: int, session_path: str):
    return build_item(
        submission,
        kind=CompletionItemKind.SESSION_ROTATE,
        timestamp=now,
        seq=next_seq,
        payload={'session_path': session_path, 'provider_session_id': Path(session_path).stem},
        cursor_kwargs={'session_path': session_path},
    )


def build_anchor_item(submission, *, now: str, next_seq: int, request_anchor: str, session_path: str):
    return build_item(
        submission,
        kind=CompletionItemKind.ANCHOR_SEEN,
        timestamp=now,
        seq=next_seq,
        payload={'turn_id': request_anchor, 'session_path': session_path or None},
        cursor_kwargs={'session_path': session_path or None},
    )


def build_snapshot_item(
    submission,
    *,
    now: str,
    next_seq: int,
    request_anchor: str,
    session_path: str,
    state: dict,
    reply,
    cleaned: str,
    is_done_text_fn,
):
    return build_item(
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


__all__ = [
    'build_anchor_item',
    'build_session_items',
    'build_session_rotate_item',
    'build_snapshot_item',
    'poll_submission',
]
