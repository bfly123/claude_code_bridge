from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from agents.models import AgentSpec, WorkspaceMode
from agents.store import AgentSpecStore
from project.ids import compute_project_id
from project.resolver import ProjectContext
from storage.paths import PathLayout

from .git_worktree import (
    branch_is_merged_into_head,
    delete_branch,
    is_registered_worktree,
    remove_registered_worktree,
    workspace_is_dirty,
)
from .planner import WorkspacePlanner


@dataclass(frozen=True)
class WorktreeAlert:
    agent_name: str
    branch_name: str | None
    workspace_path: str
    dirty: bool | None
    merged: bool | None
    registered: bool
    exists: bool
    reason: str

    @property
    def needs_merge(self) -> bool:
        return self.dirty is True or self.merged is False


@dataclass(frozen=True)
class WorkspaceRetirement:
    agent_name: str
    branch_name: str | None
    workspace_path: str
    reason: str
    removed_agent_state: bool = False


@dataclass(frozen=True)
class WorkspaceGuardSummary:
    warnings: tuple[WorktreeAlert, ...] = ()
    blockers: tuple[WorktreeAlert, ...] = ()
    retired: tuple[WorkspaceRetirement, ...] = ()


def reconcile_start_workspaces(project_root: Path, config) -> WorkspaceGuardSummary:
    root = _resolve_path(project_root)
    paths = PathLayout(root)
    project_ctx = _project_context(root)
    persisted_specs = _load_persisted_specs(paths)
    desired_specs = dict(config.agents)

    warnings: list[WorktreeAlert] = []
    blockers: list[WorktreeAlert] = []
    pending_worktree_retirements: list[tuple[AgentSpec, str, bool]] = []
    pending_state_cleanup: list[tuple[str, str]] = []

    for agent_name, persisted_spec in persisted_specs.items():
        desired_spec = desired_specs.get(agent_name)
        if persisted_spec.workspace_mode is WorkspaceMode.GIT_WORKTREE:
            reason = _retirement_reason(persisted_spec, desired_spec, project_ctx)
            if reason is None:
                continue
            alert = _inspect_worktree(root, project_ctx, persisted_spec, reason=reason)
            if alert.needs_merge:
                blockers.append(alert)
                continue
            pending_worktree_retirements.append((persisted_spec, reason, desired_spec is None))
            continue
        if desired_spec is None:
            pending_state_cleanup.append((agent_name, 'removed_from_config'))

    for spec in desired_specs.values():
        if spec.workspace_mode is not WorkspaceMode.GIT_WORKTREE:
            continue
        alert = _inspect_worktree(root, project_ctx, spec, reason='active_worktree')
        if alert.needs_merge:
            warnings.append(alert)

    if blockers:
        return WorkspaceGuardSummary(
            warnings=tuple(warnings),
            blockers=tuple(blockers),
        )

    retired: list[WorkspaceRetirement] = []
    for spec, reason, remove_agent_state in pending_worktree_retirements:
        retired.append(
            _retire_worktree_spec(
                root,
                paths,
                project_ctx,
                spec,
                reason=reason,
                remove_agent_state=remove_agent_state,
            )
        )
    for agent_name, reason in pending_state_cleanup:
        _remove_agent_state(paths, agent_name)
        retired.append(
            WorkspaceRetirement(
                agent_name=agent_name,
                branch_name=None,
                workspace_path='',
                reason=reason,
                removed_agent_state=True,
            )
        )

    return WorkspaceGuardSummary(
        warnings=tuple(warnings),
        blockers=(),
        retired=tuple(retired),
    )


def prepare_reset_workspaces(project_root: Path, *, apply: bool = True) -> WorkspaceGuardSummary:
    root = _resolve_path(project_root)
    paths = PathLayout(root)
    project_ctx = _project_context(root)

    blockers: list[WorktreeAlert] = []
    pending_retirements: list[AgentSpec] = []
    for spec in _collect_reset_worktree_specs(root, paths, project_ctx):
        alert = _inspect_worktree(root, project_ctx, spec, reason='reset_context')
        if alert.needs_merge:
            blockers.append(alert)
            continue
        pending_retirements.append(spec)

    if blockers:
        return WorkspaceGuardSummary(blockers=tuple(blockers))

    if not apply:
        return WorkspaceGuardSummary()

    retired = tuple(
        _retire_worktree_spec(
            root,
            paths,
            project_ctx,
            spec,
            reason='reset_context',
            remove_agent_state=False,
        )
        for spec in pending_retirements
    )
    return WorkspaceGuardSummary(retired=retired)


def inspect_kill_worktrees(project_root: Path) -> WorkspaceGuardSummary:
    root = _resolve_path(project_root)
    paths = PathLayout(root)
    project_ctx = _project_context(root)
    warnings = tuple(
        alert
        for spec in _load_persisted_specs(paths).values()
        if spec.workspace_mode is WorkspaceMode.GIT_WORKTREE
        for alert in (_inspect_worktree(root, project_ctx, spec, reason='kill_warning'),)
        if alert.needs_merge
    )
    return WorkspaceGuardSummary(warnings=warnings)


def format_workspace_blockers(action: str, blockers: tuple[WorktreeAlert, ...]) -> str:
    lines = [f'{action} blocked by unmerged or dirty worktree state:']
    for item in blockers:
        branch = item.branch_name or '<none>'
        dirty = _state_text(item.dirty)
        merged = _state_text(item.merged)
        lines.append(
            f'- agent={item.agent_name} reason={item.reason} branch={branch} '
            f'dirty={dirty} merged_into_head={merged} path={item.workspace_path}'
        )
    lines.append('merge or clean the listed worktree branches and retry')
    return '\n'.join(lines)


def _retirement_reason(
    persisted_spec: AgentSpec,
    desired_spec: AgentSpec | None,
    project_ctx: ProjectContext,
) -> str | None:
    if desired_spec is None:
        return 'removed_from_config'
    if desired_spec.workspace_mode is not WorkspaceMode.GIT_WORKTREE:
        return 'workspace_mode_changed'
    planner = WorkspacePlanner()
    current = planner.plan(desired_spec, project_ctx)
    persisted = planner.plan(persisted_spec, project_ctx)
    if current.workspace_path != persisted.workspace_path or current.branch_name != persisted.branch_name:
        return 'worktree_identity_changed'
    return None


def _inspect_worktree(
    project_root: Path,
    project_ctx: ProjectContext,
    spec: AgentSpec,
    *,
    reason: str,
) -> WorktreeAlert:
    plan = WorkspacePlanner().plan(spec, project_ctx)
    branch_name = plan.branch_name
    merged = branch_is_merged_into_head(project_root, branch_name) if branch_name else None
    return WorktreeAlert(
        agent_name=spec.name,
        branch_name=branch_name,
        workspace_path=str(plan.workspace_path),
        dirty=workspace_is_dirty(plan.workspace_path),
        merged=merged,
        registered=is_registered_worktree(project_root, plan.workspace_path),
        exists=plan.workspace_path.exists(),
        reason=reason,
    )


def _retire_worktree_spec(
    project_root: Path,
    paths: PathLayout,
    project_ctx: ProjectContext,
    spec: AgentSpec,
    *,
    reason: str,
    remove_agent_state: bool,
) -> WorkspaceRetirement:
    plan = WorkspacePlanner().plan(spec, project_ctx)
    removed = remove_registered_worktree(project_root, plan.workspace_path)
    if not removed and _path_within(plan.workspace_path, paths.workspaces_dir) and plan.workspace_path.exists():
        shutil.rmtree(plan.workspace_path)
    if plan.branch_name:
        delete_branch(project_root, plan.branch_name)
    if remove_agent_state:
        _remove_agent_state(paths, spec.name)
    return WorkspaceRetirement(
        agent_name=spec.name,
        branch_name=plan.branch_name,
        workspace_path=str(plan.workspace_path),
        reason=reason,
        removed_agent_state=remove_agent_state,
    )


def _remove_agent_state(paths: PathLayout, agent_name: str) -> None:
    for target in (paths.agent_dir(agent_name), paths.agent_mailbox_dir(agent_name)):
        if target.is_symlink() or target.is_file():
            target.unlink()
            continue
        if target.is_dir():
            shutil.rmtree(target)


def _load_persisted_specs(paths: PathLayout) -> dict[str, AgentSpec]:
    store = AgentSpecStore(paths)
    specs: dict[str, AgentSpec] = {}
    if not paths.agents_dir.is_dir():
        return specs
    for child in sorted(paths.agents_dir.iterdir()):
        if not child.is_dir():
            continue
        try:
            spec = store.load(child.name)
        except Exception:
            continue
        if spec is None:
            continue
        specs[spec.name] = spec
    return specs


def _collect_reset_worktree_specs(
    project_root: Path,
    paths: PathLayout,
    project_ctx: ProjectContext,
) -> tuple[AgentSpec, ...]:
    specs: list[AgentSpec] = []
    seen: set[tuple[str, str]] = set()

    def _append(spec: AgentSpec) -> None:
        if spec.workspace_mode is not WorkspaceMode.GIT_WORKTREE:
            return
        plan = WorkspacePlanner().plan(spec, project_ctx)
        identity = (str(_resolve_path(plan.workspace_path)), plan.branch_name or '')
        if identity in seen:
            return
        seen.add(identity)
        specs.append(spec)

    for spec in _load_persisted_specs(paths).values():
        _append(spec)
    for spec in _load_current_config_specs(project_root):
        _append(spec)
    return tuple(specs)


def _load_current_config_specs(project_root: Path) -> tuple[AgentSpec, ...]:
    try:
        from agents.config_loader import load_project_config

        config = load_project_config(project_root).config
    except Exception:
        return ()
    return tuple(config.agents.values())


def _project_context(project_root: Path) -> ProjectContext:
    root = _resolve_path(project_root)
    return ProjectContext(
        cwd=root,
        project_root=root,
        config_dir=root / '.ccb',
        project_id=compute_project_id(root),
        source='workspace-reconcile',
    )


def _path_within(path: Path, parent: Path) -> bool:
    try:
        _resolve_path(path).relative_to(_resolve_path(parent))
    except ValueError:
        return False
    return True


def _resolve_path(path: Path) -> Path:
    candidate = Path(path).expanduser()
    try:
        return candidate.resolve()
    except Exception:
        return candidate.absolute()


def _state_text(value: bool | None) -> str:
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    return 'unknown'


__all__ = [
    'WorkspaceGuardSummary',
    'WorkspaceRetirement',
    'WorktreeAlert',
    'format_workspace_blockers',
    'inspect_kill_worktrees',
    'prepare_reset_workspaces',
    'reconcile_start_workspaces',
]
