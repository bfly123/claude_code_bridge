from __future__ import annotations

import os
from pathlib import Path

from agents.models import normalize_agent_name
from project.discovery import (
    find_nearest_project_anchor,
    find_workspace_binding,
    load_workspace_binding,
    project_ccb_dir,
)
from provider_core.instance_resolution import named_agent_instance
from provider_core.pathing import session_filename_for_instance
from provider_sessions.files import find_project_session_file


def session_filename_matches(*, base_filename: str, filename: str) -> bool:
    name = str(filename or "").strip()
    base = str(base_filename or "").strip()
    if not name or not base:
        return False
    if name == base:
        return True
    prefix = _session_prefix(base)
    return bool(prefix and name.startswith(f"{prefix}-") and name.endswith("-session"))


def agent_name_from_session_filename(
    *,
    provider: str,
    base_filename: str,
    filename: str,
) -> str | None:
    name = str(filename or "").strip()
    base = str(base_filename or "").strip()
    if not session_filename_matches(base_filename=base, filename=name):
        return None
    if name == base:
        return None
    prefix = _session_prefix(base)
    if not prefix:
        return None
    raw = name[len(prefix) + 1 : -len("-session")]
    normalized = normalize_agent_name(raw)
    return normalized or None


def env_bound_session_file(*, base_filename: str) -> Path | None:
    raw = str(os.environ.get("CCB_SESSION_FILE") or "").strip()
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
    if allow_env:
        env_session = env_bound_session_file(base_filename=base_filename)
        if env_session is not None:
            return agent_name_from_session_filename(
                provider=provider,
                base_filename=base_filename,
                filename=env_session.name,
            )

    binding_agent = _workspace_binding_agent_name(work_dir)
    if binding_agent is not None:
        return binding_agent

    unique = _unique_project_session_file(base_filename=base_filename, work_dir=work_dir)
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
    if allow_env:
        env_session = env_bound_session_file(base_filename=base_filename)
        if env_session is not None:
            return env_session

    agent_name = resolve_bound_agent_name(
        provider=provider,
        base_filename=base_filename,
        work_dir=work_dir,
        allow_env=False,
    )
    if agent_name:
        session_file = _session_file_for_agent(
            provider=provider,
            base_filename=base_filename,
            work_dir=work_dir,
            agent_name=agent_name,
        )
        if session_file is not None:
            return session_file
        return None

    return _unique_project_session_file(base_filename=base_filename, work_dir=work_dir)


def _session_file_for_agent(
    *,
    provider: str,
    base_filename: str,
    work_dir: Path | str,
    agent_name: str,
) -> Path | None:
    instance = named_agent_instance(agent_name, primary_agent=str(provider or "").strip().lower())
    filename = session_filename_for_instance(base_filename, instance)
    try:
        root = Path(work_dir).expanduser()
    except Exception:
        return None
    return find_project_session_file(root, filename)


def _workspace_binding_agent_name(work_dir: Path | str) -> str | None:
    try:
        current = Path(work_dir).expanduser().resolve()
    except Exception:
        try:
            current = Path(work_dir).expanduser().absolute()
        except Exception:
            return None
    binding_path = find_workspace_binding(current)
    if binding_path is None:
        return None
    try:
        binding = load_workspace_binding(binding_path)
    except Exception:
        return None
    raw = binding.get("agent_name")
    if not isinstance(raw, str) or not raw.strip():
        return None
    normalized = normalize_agent_name(raw)
    return normalized or None


def _unique_project_session_file(*, base_filename: str, work_dir: Path | str) -> Path | None:
    project_root = _target_project_root(work_dir)
    if project_root is None:
        return None
    candidates = _project_session_candidates(base_filename=base_filename, project_root=project_root)
    if len(candidates) != 1:
        return None
    return candidates[0]


def _target_project_root(work_dir: Path | str) -> Path | None:
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
            target_project = Path(str(binding["target_project"])).expanduser()
            try:
                return target_project.resolve()
            except Exception:
                return target_project.absolute()
        except Exception:
            return None
    return find_nearest_project_anchor(current)


def _project_session_candidates(*, base_filename: str, project_root: Path) -> list[Path]:
    ccb_dir = project_ccb_dir(project_root)
    candidates: list[Path] = []
    base_path = ccb_dir / base_filename
    if base_path.is_file():
        candidates.append(base_path)
    pattern = _named_pattern(base_filename)
    if pattern:
        try:
            named_paths = sorted(path for path in ccb_dir.glob(pattern) if path.is_file())
        except Exception:
            named_paths = []
        candidates.extend(named_paths)
    return candidates


def _session_prefix(base_filename: str) -> str:
    base = str(base_filename or "").strip()
    if base.endswith("-session"):
        return base[: -len("-session")]
    return base


def _named_pattern(base_filename: str) -> str:
    prefix = _session_prefix(base_filename)
    if not prefix:
        return ""
    return f"{prefix}-*-session"
