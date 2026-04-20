from __future__ import annotations

from pathlib import Path

from agents.models import normalize_agent_name
from project.discovery import project_ccb_dir
from provider_core.instance_resolution import named_agent_instance
from provider_core.pathing import session_filename_for_instance
from provider_sessions.files import find_project_session_file

from .discovery_names import named_pattern
from .discovery_workspace import target_project_root


def session_file_for_agent(
    *,
    provider: str,
    base_filename: str,
    work_dir: Path | str,
    agent_name: str,
) -> Path | None:
    try:
        root = Path(work_dir).expanduser()
    except Exception:
        return None
    for instance in candidate_instances_for_agent(provider=provider, agent_name=agent_name):
        filename = session_filename_for_instance(base_filename, instance)
        session_file = find_project_session_file(root, filename)
        if session_file is not None:
            return session_file
    return None


def unique_project_session_file(*, base_filename: str, work_dir: Path | str) -> Path | None:
    project_root = target_project_root(work_dir)
    if project_root is None:
        return None
    candidates = project_session_candidates(
        base_filename=base_filename,
        project_root=project_root,
    )
    if len(candidates) != 1:
        return None
    return candidates[0]


def project_session_candidates(*, base_filename: str, project_root: Path) -> list[Path]:
    ccb_dir = project_ccb_dir(project_root)
    candidates: list[Path] = []
    base_path = ccb_dir / base_filename
    if base_path.is_file():
        candidates.append(base_path)
    pattern = named_pattern(base_filename)
    if pattern:
        try:
            named_paths = sorted(path for path in ccb_dir.glob(pattern) if path.is_file())
        except Exception:
            named_paths = []
        candidates.extend(named_paths)
    return candidates


def candidate_instances_for_agent(*, provider: str, agent_name: str) -> tuple[str | None, ...]:
    normalized_provider = str(provider or '').strip().lower()
    normalized_agent = normalize_agent_name(agent_name)
    instance = named_agent_instance(agent_name, primary_agent=normalized_provider)
    candidates: list[str | None] = []
    if instance is not None:
        candidates.append(instance)
    if normalized_agent and normalized_agent == normalized_provider and None not in candidates:
        candidates.append(None)
    if not candidates:
        candidates.append(None)
    return tuple(candidates)


__all__ = [
    'candidate_instances_for_agent',
    'project_session_candidates',
    'session_file_for_agent',
    'unique_project_session_file',
]
