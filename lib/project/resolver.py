from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from agents.config_loader import ensure_bootstrap_project_config
from project.discovery import (
    ProjectDiscoveryError,
    find_current_project_anchor,
    find_nearest_project_anchor,
    find_parent_project_anchor_dir,
    find_workspace_binding,
    is_dangerous_project_root,
    load_workspace_binding,
    project_ccb_dir,
)
from project.ids import compute_project_id


@dataclass(frozen=True)
class ProjectContext:
    cwd: Path
    project_root: Path
    config_dir: Path
    project_id: str
    source: str


class ProjectResolver:
    def resolve(
        self,
        cwd: Path,
        *,
        explicit_project: Path | None = None,
        allow_ancestor_anchor: bool = True,
    ) -> ProjectContext:
        current = _resolved_path(cwd)

        if explicit_project is not None:
            return _explicit_project_context(current, explicit_project)

        binding_path = find_workspace_binding(current)
        if binding_path is not None:
            return _workspace_binding_context(current, binding_path)

        anchor = (
            find_nearest_project_anchor(current)
            if allow_ancestor_anchor
            else find_current_project_anchor(current)
        )
        if anchor is not None:
            return _project_context(current, anchor, source='anchor')

        raise ProjectDiscoveryError(
            f'cannot resolve project for {current}; no .ccb anchor or workspace binding found'
        )


def bootstrap_project(project_root: Path) -> ProjectContext:
    root = _resolved_path(project_root)
    config_dir = project_ccb_dir(root)
    if config_dir.exists() and not config_dir.is_dir():
        raise ProjectDiscoveryError(f'invalid project anchor: {config_dir} exists but is not a directory')
    parent_anchor = find_parent_project_anchor_dir(root)
    if parent_anchor is not None:
        raise ProjectDiscoveryError(_nested_anchor_bootstrap_error(root, parent_anchor.parent))
    is_dangerous, danger_reason = is_dangerous_project_root(root)
    if is_dangerous and not _env_truthy('CCB_INIT_PROJECT_DANGEROUS'):
        raise ProjectDiscoveryError(
            f'refusing to auto-create .ccb in {danger_reason}; '
            'set CCB_INIT_PROJECT_DANGEROUS=1 to override'
        )
    config_dir.mkdir(parents=False, exist_ok=True)
    ensure_bootstrap_project_config(root)
    return _project_context(root, root, source='bootstrapped')


def _env_truthy(name: str) -> bool:
    value = str(os.environ.get(name) or '').strip().lower()
    return value in {'1', 'true', 'yes', 'on'}


def _resolved_path(path: Path) -> Path:
    current = Path(path).expanduser()
    try:
        return current.resolve()
    except Exception:
        return current.absolute()


def _project_context(cwd: Path, root: Path, *, source: str) -> ProjectContext:
    return ProjectContext(
        cwd=cwd,
        project_root=root,
        config_dir=project_ccb_dir(root),
        project_id=compute_project_id(root),
        source=source,
    )


def _explicit_project_context(cwd: Path, explicit_project: Path) -> ProjectContext:
    root = _resolved_path(explicit_project)
    _require_anchor_dir(root, reason='project anchor not found')
    return _project_context(cwd, root, source='explicit')


def _workspace_binding_context(cwd: Path, binding_path: Path) -> ProjectContext:
    binding = load_workspace_binding(binding_path)
    root = _resolved_path(Path(str(binding['target_project'])))
    _require_anchor_dir(root, reason='workspace binding points to missing project anchor')
    return _project_context(cwd, root, source='workspace-binding')


def _require_anchor_dir(root: Path, *, reason: str) -> None:
    config_dir = project_ccb_dir(root)
    if not config_dir.is_dir():
        raise ProjectDiscoveryError(f'{reason}: {config_dir}')


def _nested_anchor_bootstrap_error(project_root: Path, parent_root: Path) -> str:
    return (
        f'cannot auto-create .ccb in {project_root}: '
        f'parent project anchor already exists at {project_ccb_dir(parent_root)}; '
        '.ccb is the unique project anchor for a project tree. '
        f'If you intentionally want {project_root} to be a separate project, '
        f'create {project_ccb_dir(project_root)} manually and rerun'
    )
