from __future__ import annotations

from pathlib import Path

from project.discovery import (
    find_nearest_project_anchor,
    find_workspace_binding,
    load_workspace_binding,
    project_ccb_dir,
)
from provider_backends.claude.session import load_project_session
from provider_core.instance_resolution import named_agent_instance
from provider_core.pathing import session_filename_for_instance
from provider_core.session_binding_runtime import (
    agent_name_from_session_filename,
    find_bound_session_file,
    resolve_bound_agent_name,
)

_PROVIDER = "claude"
_BASE_FILENAME = ".claude-session"


def load_claude_session(work_dir: Path) -> object | None:
    session_file = find_bound_session_file(
        provider=_PROVIDER,
        base_filename=_BASE_FILENAME,
        work_dir=work_dir,
        allow_env=False,
    )
    if session_file is None:
        return None
    instance = _instance_from_session_file(session_file)
    return load_project_session(work_dir, instance)


def find_claude_session_file(work_dir: Path) -> Path | None:
    session_file = find_bound_session_file(
        provider=_PROVIDER,
        base_filename=_BASE_FILENAME,
        work_dir=work_dir,
        allow_env=False,
    )
    if session_file is not None:
        return session_file

    agent_name = resolve_bound_agent_name(
        provider=_PROVIDER,
        base_filename=_BASE_FILENAME,
        work_dir=work_dir,
        allow_env=False,
    )
    if not agent_name:
        return None
    project_root = _project_root_for_work_dir(work_dir)
    if project_root is None:
        return None
    instance = named_agent_instance(agent_name, primary_agent=_PROVIDER)
    filename = session_filename_for_instance(_BASE_FILENAME, instance)
    return project_ccb_dir(project_root) / filename


def _instance_from_session_file(session_file: Path) -> str | None:
    agent_name = agent_name_from_session_filename(
        provider=_PROVIDER,
        base_filename=_BASE_FILENAME,
        filename=session_file.name,
    )
    return named_agent_instance(agent_name or "", primary_agent=_PROVIDER)


def _project_root_for_work_dir(work_dir: Path) -> Path | None:
    try:
        current = Path(work_dir).expanduser().resolve()
    except Exception:
        try:
            current = Path(work_dir).expanduser().absolute()
        except Exception:
            return None
    binding_path = find_workspace_binding(current)
    if binding_path is not None:
        try:
            binding = load_workspace_binding(binding_path)
            project_root = Path(str(binding["target_project"])).expanduser()
            try:
                return project_root.resolve()
            except Exception:
                return project_root.absolute()
        except Exception:
            return None
    return find_nearest_project_anchor(current)


__all__ = ["find_claude_session_file", "load_claude_session"]
