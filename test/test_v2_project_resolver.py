from __future__ import annotations

import json
from pathlib import Path

import pytest

from project.discovery import WORKSPACE_BINDING_FILENAME
from project.resolver import ProjectResolver, bootstrap_project


def test_resolve_from_nearest_anchor(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    nested = project_root / 'src' / 'pkg'
    nested.mkdir(parents=True)
    (project_root / '.ccb').mkdir()
    context = ProjectResolver().resolve(nested)
    assert context.project_root == project_root.resolve()
    assert context.source == 'anchor'


def test_resolve_can_disable_ancestor_anchor_lookup(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    nested = project_root / 'src' / 'pkg'
    nested.mkdir(parents=True)
    (project_root / '.ccb').mkdir()

    with pytest.raises(ValueError):
        ProjectResolver().resolve(nested, allow_ancestor_anchor=False)


def test_resolve_from_explicit_project(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    other = tmp_path / 'elsewhere'
    other.mkdir()
    (project_root / '.ccb').mkdir(parents=True)
    context = ProjectResolver().resolve(other, explicit_project=project_root)
    assert context.project_root == project_root.resolve()
    assert context.source == 'explicit'


def test_resolve_from_workspace_binding(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    workspace_root = tmp_path / 'workspace' / 'agent1'
    workspace_root.mkdir(parents=True)
    (project_root / '.ccb').mkdir(parents=True)
    (workspace_root / WORKSPACE_BINDING_FILENAME).write_text(
        json.dumps({'target_project': str(project_root)}),
        encoding='utf-8',
    )
    context = ProjectResolver().resolve(workspace_root)
    assert context.project_root == project_root.resolve()
    assert context.source == 'workspace-binding'


def test_resolve_requires_existing_anchor(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ProjectResolver().resolve(tmp_path / 'missing')


def test_resolve_ignores_home_anchor_when_searching_from_subdirectory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / 'home'
    worktree = home / 'work' / 'repo'
    worktree.mkdir(parents=True)
    (home / '.ccb').mkdir()
    monkeypatch.setenv('HOME', str(home))

    with pytest.raises(ValueError):
        ProjectResolver().resolve(worktree)


def test_bootstrap_project_creates_anchor(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    context = bootstrap_project(project_root)
    assert (project_root / '.ccb').is_dir()
    assert (project_root / '.ccb' / 'ccb.config').is_file()
    assert context.source == 'bootstrapped'


def test_bootstrap_project_blocks_nested_auto_create_when_parent_anchor_exists(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    nested_root = project_root / 'nested'
    nested_root.mkdir(parents=True)
    (project_root / '.ccb').mkdir()

    with pytest.raises(ValueError, match='parent project anchor already exists'):
        bootstrap_project(nested_root)


def test_resolve_prefers_local_anchor_over_parent_anchor(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    nested_root = project_root / 'nested'
    nested_root.mkdir(parents=True)
    (project_root / '.ccb').mkdir()
    (nested_root / '.ccb').mkdir()

    context = ProjectResolver().resolve(nested_root, allow_ancestor_anchor=False)

    assert context.project_root == nested_root.resolve()
    assert context.source == 'anchor'


def test_bootstrap_project_blocks_home_directory_without_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setenv('HOME', str(home))

    with pytest.raises(ValueError, match='CCB_INIT_PROJECT_DANGEROUS'):
        bootstrap_project(home)
