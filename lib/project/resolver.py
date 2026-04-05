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
        current = Path(cwd).expanduser()
        try:
            current = current.resolve()
        except Exception:
            current = current.absolute()

        if explicit_project is not None:
            root = Path(explicit_project).expanduser()
            try:
                root = root.resolve()
            except Exception:
                root = root.absolute()
            config_dir = project_ccb_dir(root)
            if not config_dir.is_dir():
                raise ProjectDiscoveryError(f'project anchor not found: {config_dir}')
            return ProjectContext(
                cwd=current,
                project_root=root,
                config_dir=config_dir,
                project_id=compute_project_id(root),
                source='explicit',
            )

        anchor = (
            find_nearest_project_anchor(current)
            if allow_ancestor_anchor
            else find_current_project_anchor(current)
        )
        if anchor is not None:
            return ProjectContext(
                cwd=current,
                project_root=anchor,
                config_dir=project_ccb_dir(anchor),
                project_id=compute_project_id(anchor),
                source='anchor',
            )

        binding_path = find_workspace_binding(current)
        if binding_path is not None:
            binding = load_workspace_binding(binding_path)
            root = Path(str(binding['target_project'])).expanduser()
            try:
                root = root.resolve()
            except Exception:
                root = root.absolute()
            config_dir = project_ccb_dir(root)
            if not config_dir.is_dir():
                raise ProjectDiscoveryError(
                    f'workspace binding points to missing project anchor: {config_dir}'
                )
            return ProjectContext(
                cwd=current,
                project_root=root,
                config_dir=config_dir,
                project_id=compute_project_id(root),
                source='workspace-binding',
            )

        raise ProjectDiscoveryError(
            f'cannot resolve project for {current}; no .ccb anchor or workspace binding found'
        )


def bootstrap_project(project_root: Path) -> ProjectContext:
    root = Path(project_root).expanduser()
    try:
        root = root.resolve()
    except Exception:
        root = root.absolute()
    config_dir = project_ccb_dir(root)
    if config_dir.exists() and not config_dir.is_dir():
        raise ProjectDiscoveryError(f'invalid project anchor: {config_dir} exists but is not a directory')
    parent_anchor = find_parent_project_anchor_dir(root)
    if parent_anchor is not None:
        raise ProjectDiscoveryError(
            'project config directory not found in current directory, '
            f'but a parent project anchor exists at {parent_anchor.parent}; '
            'auto-create blocked to avoid accidental nesting'
        )
    is_dangerous, danger_reason = is_dangerous_project_root(root)
    if is_dangerous and not _env_truthy('CCB_INIT_PROJECT_DANGEROUS'):
        raise ProjectDiscoveryError(
            f'refusing to auto-create .ccb in {danger_reason}; '
            'set CCB_INIT_PROJECT_DANGEROUS=1 to override'
        )
    config_dir.mkdir(parents=False, exist_ok=True)
    ensure_bootstrap_project_config(root)
    return ProjectContext(
        cwd=root,
        project_root=root,
        config_dir=config_dir,
        project_id=compute_project_id(root),
        source='bootstrapped',
    )


def _env_truthy(name: str) -> bool:
    value = str(os.environ.get(name) or '').strip().lower()
    return value in {'1', 'true', 'yes', 'on'}
