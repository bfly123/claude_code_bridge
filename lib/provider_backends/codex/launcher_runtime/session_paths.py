from __future__ import annotations

import json
from pathlib import Path

from provider_core.pathing import session_filename_for_agent

from ..start_cmd import extract_resume_session_id


def load_resume_session_id(spec, runtime_dir: Path) -> str | None:
    session_path = preferred_session_path(spec, runtime_dir)
    if session_path is None:
        return None
    data = read_session_payload(session_path)
    if data is None:
        return None
    return payload_resume_session_id(data)


def agent_session_path(spec, runtime_dir: Path) -> Path | None:
    ccb_dir = find_project_ccb_dir(runtime_dir)
    if ccb_dir is None:
        return None
    return ccb_dir / session_filename_for_agent('codex', spec.name)


def find_project_ccb_dir(runtime_dir: Path) -> Path | None:
    current = Path(runtime_dir)
    for parent in (current, *current.parents):
        if parent.name == '.ccb':
            return parent
    return None


def session_file_for_runtime_dir(runtime_dir: Path) -> Path | None:
    ccb_dir = find_project_ccb_dir(runtime_dir)
    if ccb_dir is None:
        return None
    try:
        agent_name = runtime_dir.parents[1].name
    except Exception:
        return None
    agent_name = str(agent_name or '').strip()
    if not agent_name:
        return None
    return ccb_dir / session_filename_for_agent('codex', agent_name)


def preferred_session_path(spec, runtime_dir: Path) -> Path | None:
    candidates = (agent_session_path(spec, runtime_dir),)
    for session_path in candidates:
        if session_path is not None and session_path.is_file():
            return session_path
    return None


def read_session_payload(session_path: Path) -> dict | None:
    try:
        data = json.loads(session_path.read_text(encoding='utf-8'))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def payload_resume_session_id(data: dict) -> str | None:
    session_id = str(data.get('codex_session_id') or '').strip()
    if session_id:
        return session_id
    start_cmd = str(data.get('codex_start_cmd') or data.get('start_cmd') or '').strip()
    if not start_cmd:
        return None
    return extract_resume_session_id(start_cmd)


__all__ = ['load_resume_session_id', 'session_file_for_runtime_dir']
