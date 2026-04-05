from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from provider_core.protocol import ANY_REQ_ID_PATTERN, REQ_ID_BOUNDARY_PATTERN
from storage.atomic import atomic_write_json

SCHEMA_VERSION = 1
REQ_ID_RE = re.compile(rf'CCB_REQ_ID:\s*({ANY_REQ_ID_PATTERN}){REQ_ID_BOUNDARY_PATTERN}', re.IGNORECASE)


def extract_req_id(text: str) -> str | None:
    match = REQ_ID_RE.search(str(text or ''))
    if not match:
        return None
    return str(match.group(1) or '').strip() or None


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
    now = datetime.now(timezone.utc).isoformat()
    payload = {
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
        'timestamp': now,
    }
    path = event_path(completion_dir, req_id)
    atomic_write_json(path, payload)
    return path


def completion_dir_from_session_data(session_data: dict[str, Any]) -> Path | None:
    explicit = str(session_data.get('completion_artifact_dir') or '').strip()
    if explicit:
        return Path(explicit).expanduser()
    runtime_dir = str(session_data.get('runtime_dir') or '').strip()
    if runtime_dir:
        return Path(runtime_dir).expanduser() / 'completion'
    return None


def latest_req_id_from_transcript(transcript_path: str | Path | None) -> str | None:
    raw = str(transcript_path or '').strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return None
    matches = REQ_ID_RE.findall(content)
    if not matches:
        return None
    return str(matches[-1] or '').strip() or None
