from __future__ import annotations

from pathlib import Path

from provider_core.instance_resolution import named_agent_instance
from provider_execution.common import normalize_session_path


def load_session(work_dir: Path, *, agent_name: str, primary_agent: str, load_project_session_fn):
    instance = named_agent_instance(agent_name, primary_agent=primary_agent)
    if instance is not None:
        session = load_project_session_fn(work_dir, instance)
        if session is not None:
            return session
        return None
    return load_project_session_fn(work_dir)


def state_session_path(state: dict[str, object]) -> str:
    return normalize_session_path(state.get("session_path"))


__all__ = ["load_session", "state_session_path"]
