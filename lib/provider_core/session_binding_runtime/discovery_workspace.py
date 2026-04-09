from __future__ import annotations

from pathlib import Path

from agents.models import normalize_agent_name
from project.discovery import (
    find_nearest_project_anchor,
    find_workspace_binding,
    load_workspace_binding,
)


def resolve_work_dir(work_dir: Path | str) -> Path | None:
    try:
        return Path(work_dir).expanduser().resolve()
    except Exception:
        try:
            return Path(work_dir).expanduser().absolute()
        except Exception:
            return None


def workspace_binding(work_dir: Path | str) -> tuple[Path | None, dict | None]:
    current = resolve_work_dir(work_dir)
    if current is None:
        return None, None
    binding_path = find_workspace_binding(current)
    if binding_path is None:
        return current, None
    try:
        return current, load_workspace_binding(binding_path)
    except Exception:
        return current, None


def workspace_binding_agent_name(work_dir: Path | str) -> str | None:
    _current, binding = workspace_binding(work_dir)
    if binding is None:
        return None
    raw = binding.get('agent_name')
    if not isinstance(raw, str) or not raw.strip():
        return None
    normalized = normalize_agent_name(raw)
    return normalized or None


def binding_target_project(binding: dict) -> Path | None:
    try:
        target_project = Path(str(binding['target_project'])).expanduser()
    except Exception:
        return None
    try:
        return target_project.resolve()
    except Exception:
        try:
            return target_project.absolute()
        except Exception:
            return None


def target_project_root(work_dir: Path | str) -> Path | None:
    current, binding = workspace_binding(work_dir)
    if current is None:
        return None
    if binding is not None:
        return binding_target_project(binding)
    return find_nearest_project_anchor(current)


__all__ = [
    'binding_target_project',
    'resolve_work_dir',
    'target_project_root',
    'workspace_binding',
    'workspace_binding_agent_name',
]
