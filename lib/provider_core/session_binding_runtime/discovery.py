from __future__ import annotations

import os
from pathlib import Path

from provider_core.instance_resolution import named_agent_instance
from .discovery_candidates import session_file_for_agent, unique_project_session_file
from .discovery_names import (
    agent_name_from_session_filename,
    normalized_filename,
    session_filename_matches,
)
from .discovery_workspace import workspace_binding_agent_name


def env_bound_session_file(*, base_filename: str) -> Path | None:
    raw = normalized_filename(os.environ.get('CCB_SESSION_FILE') or '')
    if not raw:
        return None
    try:
        session_path = Path(os.path.expanduser(raw))
    except Exception:
        return None
    if not session_path.is_file():
        return None
    if not session_filename_matches(base_filename=base_filename, filename=session_path.name):
        return None
    return session_path


def resolve_bound_agent_name(
    *,
    provider: str,
    base_filename: str,
    work_dir: Path | str,
    allow_env: bool = True,
) -> str | None:
    env_agent = _env_bound_agent_name(
        provider=provider,
        base_filename=base_filename,
        allow_env=allow_env,
    )
    if env_agent is not None:
        return env_agent
    binding_agent = workspace_binding_agent_name(work_dir)
    if binding_agent is not None:
        return binding_agent

    unique = unique_project_session_file(base_filename=base_filename, work_dir=work_dir)
    if unique is not None:
        return agent_name_from_session_filename(
            provider=provider,
            base_filename=base_filename,
            filename=unique.name,
        )
    return None


def resolve_bound_instance(
    *,
    provider: str,
    base_filename: str,
    work_dir: Path | str,
    allow_env: bool = True,
) -> str | None:
    agent_name = resolve_bound_agent_name(
        provider=provider,
        base_filename=base_filename,
        work_dir=work_dir,
        allow_env=allow_env,
    )
    if not agent_name:
        return None
    return named_agent_instance(agent_name, primary_agent=str(provider or "").strip().lower())


def find_bound_session_file(
    *,
    provider: str,
    base_filename: str,
    work_dir: Path | str,
    allow_env: bool = True,
) -> Path | None:
    env_session = _env_bound_session_file(base_filename=base_filename, allow_env=allow_env)
    if env_session is not None:
        return env_session
    agent_name = resolve_bound_agent_name(
        provider=provider,
        base_filename=base_filename,
        work_dir=work_dir,
        allow_env=False,
    )
    if agent_name:
        session_file = session_file_for_agent(
            provider=provider,
            base_filename=base_filename,
            work_dir=work_dir,
            agent_name=agent_name,
        )
        if session_file is not None:
            return session_file
        return None
    return unique_project_session_file(base_filename=base_filename, work_dir=work_dir)


def _env_bound_session_file(*, base_filename: str, allow_env: bool) -> Path | None:
    if not allow_env:
        return None
    return env_bound_session_file(base_filename=base_filename)


def _env_bound_agent_name(*, provider: str, base_filename: str, allow_env: bool) -> str | None:
    env_session = _env_bound_session_file(base_filename=base_filename, allow_env=allow_env)
    if env_session is None:
        return None
    return agent_name_from_session_filename(
        provider=provider,
        base_filename=base_filename,
        filename=env_session.name,
    )
