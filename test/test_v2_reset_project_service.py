from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from agents.models import PermissionMode, QueuePolicy, RestoreMode, RuntimeMode, WorkspaceMode
from agents.models import AgentSpec
from cli.services.reset_project import reset_project_state
from project.resolver import bootstrap_project
from workspace.materializer import WorkspaceMaterializer
from workspace.planner import WorkspacePlanner


def _spec() -> AgentSpec:
    return AgentSpec(
        name='agent1',
        provider='codex',
        target='.',
        workspace_mode=WorkspaceMode.GIT_WORKTREE,
        workspace_root=None,
        runtime_mode=RuntimeMode.PANE_BACKED,
        restore_default=RestoreMode.AUTO,
        permission_default=PermissionMode.MANUAL,
        queue_policy=QueuePolicy.SERIAL_PER_AGENT,
        branch_template=None,
    )


def test_reset_project_state_preserves_only_ccb_config(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-reset'
    ccb_dir = project_root / '.ccb'
    ccb_dir.mkdir(parents=True)
    (ccb_dir / 'ccb.config').write_text('cmd; agent1:codex, agent2:claude\n', encoding='utf-8')
    (ccb_dir / 'ccbd' / 'state.json').parent.mkdir(parents=True, exist_ok=True)
    (ccb_dir / 'ccbd' / 'state.json').write_text('{}', encoding='utf-8')
    (ccb_dir / 'agents' / 'agent1' / 'runtime.json').parent.mkdir(parents=True, exist_ok=True)
    (ccb_dir / 'agents' / 'agent1' / 'runtime.json').write_text('{}', encoding='utf-8')
    (ccb_dir / 'workspaces' / 'agent1' / 'memory.txt').parent.mkdir(parents=True, exist_ok=True)
    (ccb_dir / 'workspaces' / 'agent1' / 'memory.txt').write_text('old', encoding='utf-8')
    (ccb_dir / '.codex-agent1-session').write_text('session', encoding='utf-8')

    seen: dict[str, object] = {}

    def _fake_stop(context) -> None:
        seen['project_root'] = context.project.project_root

    monkeypatch.setattr('cli.services.reset_project._stop_project_runtime', _fake_stop)

    summary = reset_project_state(project_root)

    assert summary.reset_performed is True
    assert summary.preserved_config is True
    assert seen['project_root'] == project_root.resolve()
    assert ccb_dir.is_dir()
    assert (ccb_dir / 'ccb.config').read_text(encoding='utf-8') == 'cmd; agent1:codex, agent2:claude\n'
    assert sorted(path.relative_to(ccb_dir).as_posix() for path in ccb_dir.rglob('*') if path.is_file()) == ['ccb.config']


def test_reset_project_state_fails_fast_when_runtime_cleanup_cannot_stop_project(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-reset-fails'
    ccb_dir = project_root / '.ccb'
    ccb_dir.mkdir(parents=True)
    (ccb_dir / 'ccb.config').write_text('cmd; agent1:codex\n', encoding='utf-8')
    (ccb_dir / 'agents' / 'agent1' / 'runtime.json').parent.mkdir(parents=True, exist_ok=True)
    (ccb_dir / 'agents' / 'agent1' / 'runtime.json').write_text('{}', encoding='utf-8')

    def _raise(label: str):
        def _inner(*args, **kwargs):
            del args, kwargs
            raise RuntimeError(f'{label} failed')
        return _inner

    class _FailingNamespaceController:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def destroy(self, *args, **kwargs) -> None:
            del args, kwargs
            raise RuntimeError('namespace failed')

    monkeypatch.setattr('cli.services.reset_project.kill_project', _raise('kill'))
    monkeypatch.setattr('cli.services.reset_project.shutdown_daemon', _raise('shutdown'))
    monkeypatch.setattr('cli.services.reset_project.ProjectNamespaceController', _FailingNamespaceController)

    with pytest.raises(RuntimeError, match='ccb kill -f'):
        reset_project_state(project_root)

    assert ccb_dir.is_dir()
    assert (ccb_dir / 'ccb.config').read_text(encoding='utf-8') == 'cmd; agent1:codex\n'
    assert (ccb_dir / 'agents' / 'agent1' / 'runtime.json').is_file()


def test_reset_project_state_unregisters_git_worktrees_before_clearing_anchor(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-reset-git-worktree'
    project_root.mkdir(parents=True)
    (project_root / 'README.md').write_text('hello\n', encoding='utf-8')
    subprocess.run(['git', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=project_root, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=project_root, check=True)
    subprocess.run(['git', 'add', '.'], cwd=project_root, check=True)
    subprocess.run(['git', 'commit', '-m', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    ccb_dir = project_root / '.ccb'
    ccb_dir.mkdir(parents=True, exist_ok=True)
    (ccb_dir / 'ccb.config').write_text('agent1:codex\n', encoding='utf-8')

    ctx = bootstrap_project(project_root)
    plan = WorkspacePlanner().plan(_spec(), ctx)
    WorkspaceMaterializer().materialize(plan)
    assert plan.workspace_path.exists()

    monkeypatch.setattr('cli.services.reset_project._stop_project_runtime', lambda context: None)

    summary = reset_project_state(project_root)

    assert summary.reset_performed is True
    assert (ccb_dir / 'ccb.config').read_text(encoding='utf-8') == 'agent1:codex\n'
    assert plan.workspace_path.exists() is False

    worktrees = subprocess.run(
        ['git', '-C', str(project_root), 'worktree', 'list', '--porcelain'],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout
    assert str(plan.workspace_path) not in worktrees

    rebuilt_ctx = bootstrap_project(project_root)
    rebuilt_plan = WorkspacePlanner().plan(_spec(), rebuilt_ctx)
    result = WorkspaceMaterializer().materialize(rebuilt_plan)

    assert result.created is True
    assert rebuilt_plan.workspace_path.exists()


def test_reset_project_state_blocks_unmerged_worktree_before_runtime_stop(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-reset-block-worktree'
    project_root.mkdir(parents=True)
    (project_root / 'README.md').write_text('hello\n', encoding='utf-8')
    subprocess.run(['git', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=project_root, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=project_root, check=True)
    subprocess.run(['git', 'add', '.'], cwd=project_root, check=True)
    subprocess.run(['git', 'commit', '-m', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    ccb_dir = project_root / '.ccb'
    ccb_dir.mkdir(parents=True, exist_ok=True)
    (ccb_dir / 'ccb.config').write_text('agent1:codex(worktree)\n', encoding='utf-8')

    ctx = bootstrap_project(project_root)
    plan = WorkspacePlanner().plan(_spec(), ctx)
    WorkspaceMaterializer().materialize(plan)
    (plan.workspace_path / 'feature.txt').write_text('worktree-only\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(plan.workspace_path), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(plan.workspace_path), 'commit', '-m', 'worktree'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    seen: dict[str, object] = {}

    def _fake_stop(context) -> None:
        seen['stopped'] = context.project.project_root

    monkeypatch.setattr('cli.services.reset_project._stop_project_runtime', _fake_stop)

    with pytest.raises(RuntimeError, match='ccb -n blocked'):
        reset_project_state(project_root)

    assert seen == {}
    assert plan.workspace_path.exists() is True
    assert ccb_dir.exists() is True
