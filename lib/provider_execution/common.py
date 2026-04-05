from __future__ import annotations

import base64
from pathlib import Path

from ccbd.api_models import JobRecord
from completion.models import CompletionCursor, CompletionItem, CompletionItemKind, CompletionSourceKind

from .base import ProviderSubmission


def build_item(
    submission: ProviderSubmission,
    *,
    kind: CompletionItemKind,
    timestamp: str,
    seq: int,
    payload: dict[str, object],
    cursor_kwargs: dict[str, object] | None = None,
) -> CompletionItem:
    cursor_payload = {'source_kind': submission.source_kind, 'event_seq': seq, 'updated_at': timestamp}
    if cursor_kwargs:
        cursor_payload.update(cursor_kwargs)
    return CompletionItem(
        kind=kind,
        timestamp=timestamp,
        cursor=CompletionCursor(**cursor_payload),
        provider=submission.provider,
        agent_name=submission.agent_name,
        req_id=submission.job_id,
        payload=payload,
    )


def request_anchor_from_runtime_state(runtime_state: dict[str, object] | None, *, fallback: str | None = None) -> str:
    if not isinstance(runtime_state, dict):
        return str(fallback or '').strip()
    anchor = str(runtime_state.get('request_anchor') or runtime_state.get('req_id') or fallback or '').strip()
    return anchor


def passive_submission(
    job: JobRecord,
    *,
    provider: str,
    now: str,
    source_kind: CompletionSourceKind,
    reason: str,
) -> ProviderSubmission:
    return ProviderSubmission(
        job_id=job.job_id,
        agent_name=job.agent_name,
        provider=provider,
        accepted_at=now,
        ready_at=now,
        source_kind=source_kind,
        reply='',
        diagnostics={'provider': provider, 'mode': 'passive', 'reason': reason},
        runtime_state={'mode': 'passive', 'reason': reason},
    )


def error_submission(
    job: JobRecord,
    *,
    provider: str,
    now: str,
    source_kind: CompletionSourceKind,
    reason: str,
    error: str,
) -> ProviderSubmission:
    return ProviderSubmission(
        job_id=job.job_id,
        agent_name=job.agent_name,
        provider=provider,
        accepted_at=now,
        ready_at=now,
        source_kind=source_kind,
        reply='',
        diagnostics={'provider': provider, 'mode': 'error', 'reason': reason, 'error': error},
        runtime_state={'mode': 'error', 'reason': reason, 'error': error, 'next_seq': 1},
    )


def normalize_session_path(value: object) -> str:
    if isinstance(value, Path):
        return str(value.expanduser())
    if isinstance(value, str) and value.strip():
        try:
            return str(Path(value).expanduser())
        except Exception:
            return value.strip()
    return ''


def preferred_session_path(session_path: str, session_ref: str | None) -> Path | None:
    if session_path.strip():
        try:
            return Path(session_path).expanduser()
        except Exception:
            return None
    ref = str(session_ref or '').strip()
    if not ref:
        return None
    if '.json' not in ref and '.jsonl' not in ref and '/' not in ref and '\\' not in ref and not ref.startswith('~'):
        return None
    try:
        return Path(ref).expanduser()
    except Exception:
        return None


def send_prompt_to_runtime_target(backend: object, pane_id: str, text: str) -> None:
    strict_send = getattr(backend, 'send_text_to_pane', None)
    if callable(strict_send):
        strict_send(pane_id, text)
        return
    send_text = getattr(backend, 'send_text', None)
    if callable(send_text):
        send_text(pane_id, text)
        return
    raise RuntimeError('terminal backend does not support text submission')


def is_runtime_target_alive(backend: object, pane_id: str) -> bool:
    strict_check = getattr(backend, 'is_tmux_pane_alive', None)
    if callable(strict_check):
        return bool(strict_check(pane_id))
    is_alive = getattr(backend, 'is_alive', None)
    if callable(is_alive):
        return bool(is_alive(pane_id))
    return False


def serialize_runtime_state(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return {'__ccb_type__': 'path', 'value': str(value.expanduser())}
    if isinstance(value, bytes):
        return {'__ccb_type__': 'bytes', 'value': base64.b64encode(value).decode('ascii')}
    if isinstance(value, tuple):
        return {'__ccb_type__': 'tuple', 'items': [serialize_runtime_state(item) for item in value]}
    if isinstance(value, list):
        return [serialize_runtime_state(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize_runtime_state(item) for key, item in value.items()}
    return str(value)


def deserialize_runtime_state(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [deserialize_runtime_state(item) for item in value]
    if isinstance(value, dict):
        marker = value.get('__ccb_type__')
        if marker == 'path':
            return Path(str(value.get('value') or '')).expanduser()
        if marker == 'bytes':
            encoded = str(value.get('value') or '')
            return base64.b64decode(encoded.encode('ascii')) if encoded else b''
        if marker == 'tuple':
            return tuple(deserialize_runtime_state(item) for item in value.get('items', []))
        return {str(key): deserialize_runtime_state(item) for key, item in value.items()}
    return value
