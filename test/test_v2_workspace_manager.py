from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from agents.models import AgentSpec, PermissionMode, QueuePolicy, RestoreMode, RuntimeMode, WorkspaceMode
from project.resolver import bootstrap_project
from workspace.binding import WorkspaceBindingStore
from workspace.materializer import WorkspaceMaterializer
from workspace.planner import WorkspacePlanner
from workspace.validator import WorkspaceValidator


def _spec(
    *,
    workspace_mode: WorkspaceMode = WorkspaceMode.GIT_WORKTREE,
    workspace_root: str | None = None,
    branch_template: str | None = None,
) -> AgentSpec:
    return AgentSpec(
        name='agent1',
        provider='codex',
        target='.',
        workspace_mode=workspace_mode,
        workspace_root=workspace_root,
        runtime_mode=RuntimeMode.PANE_BACKED,
        restore_default=RestoreMode.AUTO,
        permission_default=PermissionMode.MANUAL,
        queue_policy=QueuePolicy.SERIAL_PER_AGENT,
        branch_template=branch_template,
    )


def test_workspace_planner_builds_git_worktree_plan(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)

    plan = WorkspacePlanner().plan(_spec(), ctx)
    assert plan.workspace_mode is WorkspaceMode.GIT_WORKTREE
    assert plan.workspace_path == (project_root / '.ccb' / 'workspaces' / 'agent1').resolve()
    assert plan.branch_name == 'ccb/agent1'
    assert plan.binding_path is not None


def test_workspace_planner_supports_external_root_and_custom_branch_template(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    external = tmp_path / 'ws'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)

    plan = WorkspacePlanner().plan(
        _spec(workspace_root=str(external), branch_template='ccb/{project_slug}/{agent_name}'),
        ctx,
    )
    assert external.resolve() in plan.workspace_path.parents
    assert plan.branch_name is not None
    assert 'agent1' in plan.branch_name


def test_workspace_planner_inplace_uses_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)

    plan = WorkspacePlanner().plan(_spec(workspace_mode=WorkspaceMode.INPLACE), ctx)
    assert plan.workspace_path == project_root.resolve()
    assert plan.binding_path is None
    assert plan.unsafe_shared_workspace is True


def test_workspace_planner_rejects_unknown_branch_template_var(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)

    with pytest.raises(ValueError):
        WorkspacePlanner().plan(_spec(branch_template='ccb/{unknown}'), ctx)


def test_workspace_binding_and_validator_roundtrip(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    plan = WorkspacePlanner().plan(_spec(), ctx)
    plan.workspace_path.mkdir(parents=True)

    binding_path = WorkspaceBindingStore().save(plan)
    assert binding_path is not None and binding_path.exists()
    result = WorkspaceValidator().validate(plan)
    assert result.ok is True
    assert result.errors == ()


def test_workspace_validator_reports_missing_binding(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    ctx = bootstrap_project(project_root)
    plan = WorkspacePlanner().plan(_spec(), ctx)
    plan.workspace_path.mkdir(parents=True)

    result = WorkspaceValidator().validate(plan)
    assert result.ok is True
    assert result.warnings == ('workspace binding file is missing',)


def test_workspace_materializer_creates_real_git_worktree(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    (project_root / 'README.md').write_text('hello\n', encoding='utf-8')
    subprocess.run(['git', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=project_root, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=project_root, check=True)
    subprocess.run(['git', 'add', '.'], cwd=project_root, check=True)
    subprocess.run(['git', 'commit', '-m', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    ctx = bootstrap_project(project_root)
    plan = WorkspacePlanner().plan(_spec(), ctx)

    result = WorkspaceMaterializer().materialize(plan)

    assert result.created is True
    assert (plan.workspace_path / '.git').exists()
    assert (plan.workspace_path / 'README.md').read_text(encoding='utf-8') == 'hello\n'
    branch = subprocess.run(
        ['git', '-C', str(plan.workspace_path), 'branch', '--show-current'],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    assert branch == 'ccb/agent1'


def test_workspace_materializer_falls_back_to_copy_for_non_git_project(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    (project_root / 'README.md').write_text('copy\n', encoding='utf-8')
    ctx = bootstrap_project(project_root)
    plan = WorkspacePlanner().plan(_spec(), ctx)

    result = WorkspaceMaterializer().materialize(plan)

    assert result.created is True
    assert (plan.workspace_path / 'README.md').read_text(encoding='utf-8') == 'copy\n'
    assert not (plan.workspace_path / '.git').exists()


def test_workspace_materializer_clears_placeholder_binding_before_worktree_add(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    (project_root / 'README.md').write_text('hello\n', encoding='utf-8')
    subprocess.run(['git', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=project_root, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=project_root, check=True)
    subprocess.run(['git', 'add', '.'], cwd=project_root, check=True)
    subprocess.run(['git', 'commit', '-m', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    ctx = bootstrap_project(project_root)
    plan = WorkspacePlanner().plan(_spec(), ctx)
    plan.workspace_path.mkdir(parents=True)
    assert plan.binding_path is not None
    plan.binding_path.write_text('{}\n', encoding='utf-8')

    WorkspaceMaterializer().materialize(plan)

    assert (plan.workspace_path / '.git').exists()
    assert not plan.binding_path.exists()


def test_workspace_materializer_recovers_missing_registered_git_worktree(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    (project_root / 'README.md').write_text('hello\n', encoding='utf-8')
    subprocess.run(['git', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=project_root, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=project_root, check=True)
    subprocess.run(['git', 'add', '.'], cwd=project_root, check=True)
    subprocess.run(['git', 'commit', '-m', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    ctx = bootstrap_project(project_root)
    plan = WorkspacePlanner().plan(_spec(), ctx)
    materializer = WorkspaceMaterializer()

    materializer.materialize(plan)
    shutil.rmtree(plan.workspace_path)

    listing_before = subprocess.run(
        ['git', '-C', str(project_root), 'worktree', 'list', '--porcelain'],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout
    assert str(plan.workspace_path) in listing_before
    assert 'prunable ' in listing_before

    result = materializer.materialize(plan)

    assert result.created is True
    assert (plan.workspace_path / '.git').exists()
    assert (plan.workspace_path / 'README.md').read_text(encoding='utf-8') == 'hello\n'
