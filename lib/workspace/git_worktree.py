from __future__ import annotations

from pathlib import Path
import subprocess


def can_use_git_worktree(repo_root: Path) -> bool:
    result = _git(repo_root, ['rev-parse', '--show-toplevel'])
    return result.returncode == 0


def has_missing_registered_worktree(repo_root: Path, workspace_path: Path) -> bool:
    target = _normalize_path(workspace_path)
    if target.exists():
        return False
    return any(path == target for path in list_registered_worktrees(repo_root))


def prune_missing_worktrees_under(repo_root: Path, workspaces_root: Path) -> bool:
    missing = tuple(
        path
        for path in list_registered_worktrees(repo_root)
        if _path_within(path, workspaces_root) and not path.exists()
    )
    if not missing:
        return False
    _run_git(repo_root, ['worktree', 'prune'], error='failed to prune stale git worktrees')
    return True


def unregister_worktrees_under(repo_root: Path, workspaces_root: Path) -> None:
    existing = tuple(
        path
        for path in list_registered_worktrees(repo_root)
        if _path_within(path, workspaces_root) and path.exists()
    )
    for path in existing:
        _run_git(
            repo_root,
            ['worktree', 'remove', '--force', str(path)],
            error=f'failed to remove git worktree {path}',
        )
    prune_missing_worktrees_under(repo_root, workspaces_root)


def branch_exists(repo_root: Path, branch_name: str) -> bool:
    result = _git(repo_root, ['show-ref', '--verify', '--quiet', f'refs/heads/{branch_name}'])
    return result.returncode == 0


def branch_is_merged_into_head(repo_root: Path, branch_name: str) -> bool | None:
    if not branch_exists(repo_root, branch_name):
        return None
    result = _git(repo_root, ['merge-base', '--is-ancestor', branch_name, 'HEAD'])
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise RuntimeError(_detail(result) or f'failed to inspect merge state for {branch_name}')


def delete_branch(repo_root: Path, branch_name: str) -> bool:
    if not branch_exists(repo_root, branch_name):
        return False
    _run_git(repo_root, ['branch', '-d', branch_name], error=f'failed to delete merged branch {branch_name}')
    return True


def list_registered_worktrees(repo_root: Path) -> tuple[Path, ...]:
    if not can_use_git_worktree(repo_root):
        return ()
    result = _git(repo_root, ['worktree', 'list', '--porcelain'])
    if result.returncode != 0:
        raise RuntimeError(_detail(result) or 'failed to list git worktrees')

    worktrees: list[Path] = []
    for raw_line in (result.stdout or '').splitlines():
        line = raw_line.strip()
        if not line.startswith('worktree '):
            continue
        worktrees.append(_normalize_path(Path(line[len('worktree ') :])))
    return tuple(worktrees)


def is_registered_worktree(repo_root: Path, workspace_path: Path) -> bool:
    target = _normalize_path(workspace_path)
    return any(path == target for path in list_registered_worktrees(repo_root))


def is_git_workspace_root(workspace_path: Path) -> bool:
    git_dir = workspace_path / '.git'
    return git_dir.exists()


def workspace_is_dirty(workspace_path: Path) -> bool | None:
    target = _normalize_path(workspace_path)
    if not target.exists() or not is_git_workspace_root(target):
        return None
    result = subprocess.run(
        ['git', '-C', str(target), 'status', '--porcelain'],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(_detail(result) or f'failed to inspect workspace status: {target}')
    return bool((result.stdout or '').strip())


def remove_registered_worktree(repo_root: Path, workspace_path: Path) -> bool:
    target = _normalize_path(workspace_path)
    if is_registered_worktree(repo_root, target):
        if target.exists():
            _run_git(repo_root, ['worktree', 'remove', '--force', str(target)], error=f'failed to remove git worktree {target}')
        else:
            prune_missing_worktrees_under(repo_root, target.parent)
        return True
    return False


def _path_within(path: Path, parent: Path) -> bool:
    normalized_path = _normalize_path(path)
    normalized_parent = _normalize_path(parent)
    try:
        normalized_path.relative_to(normalized_parent)
    except ValueError:
        return False
    return True


def _normalize_path(path: Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['git', '-C', str(repo_root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _detail(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or '').strip()


def _run_git(repo_root: Path, args: list[str], *, error: str) -> None:
    result = _git(repo_root, args)
    if result.returncode != 0:
        raise RuntimeError(f'{error}: {_detail(result)}')


__all__ = [
    'branch_exists',
    'branch_is_merged_into_head',
    'can_use_git_worktree',
    'delete_branch',
    'has_missing_registered_worktree',
    'is_git_workspace_root',
    'is_registered_worktree',
    'list_registered_worktrees',
    'prune_missing_worktrees_under',
    'remove_registered_worktree',
    'unregister_worktrees_under',
    'workspace_is_dirty',
]
