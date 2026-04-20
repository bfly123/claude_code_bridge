from __future__ import annotations

from pathlib import Path

from provider_core.instance_resolution import named_agent_instance
from provider_execution.common import normalize_session_path, preferred_session_path
from provider_hooks.artifacts import completion_dir_from_session_data


def load_session(load_project_session_fn, work_dir: Path, *, agent_name: str):
    instance = named_agent_instance(agent_name, primary_agent='gemini')
    if instance is not None:
        session = load_project_session_fn(work_dir, instance)
        if session is not None:
            return session
        return None
    return load_project_session_fn(work_dir)


def state_session_path(state: dict[str, object]) -> str:
    return normalize_session_path(state.get('session_path'))


def completion_dir_for_session(session) -> str:
    path = completion_dir_from_session_data(dict(getattr(session, 'data', {}) or {}))
    return str(path) if path is not None else ''


def configure_resume_reader(reader, state: dict[str, object], context) -> None:
    preferred_session = preferred_session_path(
        str(state.get('session_path') or ''),
        context.session_ref,
    )
    if preferred_session is not None:
        reader.set_preferred_session(preferred_session)


__all__ = [
    'completion_dir_for_session',
    'configure_resume_reader',
    'load_session',
    'state_session_path',
]
