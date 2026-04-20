from __future__ import annotations

from pathlib import Path

from project.discovery import find_workspace_binding
from workspace.binding import WorkspaceBindingStore


def resolve_workspace_actor(cwd: Path, *, project_id: str | None = None) -> str | None:
    current = _resolve_path(cwd)
    binding_path = find_workspace_binding(current)
    if binding_path is None:
        return None

    binding = WorkspaceBindingStore().load(binding_path)
    if project_id is not None and binding.project_id != project_id:
        return None

    workspace_root = _resolve_path(Path(binding.workspace_path))
    if current != workspace_root and workspace_root not in current.parents:
        return None
    return binding.agent_name


def _resolve_path(path: Path) -> Path:
    current = Path(path).expanduser()
    try:
        return current.resolve()
    except Exception:
        return current.absolute()


__all__ = ['resolve_workspace_actor']
