from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from storage.atomic import atomic_write_json

SCHEMA_VERSION = 1


def event_path(completion_dir: Path | str, req_id: str) -> Path:
    return Path(completion_dir).expanduser() / 'events' / f'{req_id}.json'


def load_event(completion_dir: Path | str, req_id: str) -> dict[str, Any] | None:
    path = event_path(completion_dir, req_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get('req_id') or '').strip() != str(req_id or '').strip():
        return None
    return payload


def write_event(
    *,
    provider: str,
    completion_dir: Path | str,
    agent_name: str,
    workspace_path: str,
    req_id: str,
    status: str,
    reply: str,
    session_id: str | None = None,
    hook_event_name: str | None = None,
    transcript_path: str | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> Path:
    payload = _event_payload(
        provider=provider,
        agent_name=agent_name,
        workspace_path=workspace_path,
        req_id=req_id,
        status=status,
        reply=reply,
        session_id=session_id,
        hook_event_name=hook_event_name,
        transcript_path=transcript_path,
        diagnostics=diagnostics,
    )
    path = event_path(completion_dir, req_id)
    atomic_write_json(path, payload)
    return path


def _event_payload(
    *,
    provider: str,
    agent_name: str,
    workspace_path: str,
    req_id: str,
    status: str,
    reply: str,
    session_id: str | None,
    hook_event_name: str | None,
    transcript_path: str | None,
    diagnostics: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        'schema_version': SCHEMA_VERSION,
        'record_type': 'provider_completion_hook',
        'provider': str(provider or '').strip().lower(),
        'agent_name': str(agent_name or '').strip(),
        'workspace_path': str(workspace_path or '').strip(),
        'req_id': str(req_id or '').strip(),
        'status': str(status or '').strip().lower(),
        'reply': str(reply or ''),
        'session_id': str(session_id or '').strip() or None,
        'hook_event_name': str(hook_event_name or '').strip() or None,
        'transcript_path': str(transcript_path or '').strip() or None,
        'diagnostics': dict(diagnostics or {}),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


__all__ = ['SCHEMA_VERSION', 'event_path', 'load_event', 'write_event']
