from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli.context import CliContextBuilder
from cli.models import ParsedConfigValidateCommand, ParsedStartCommand
from project.discovery import WORKSPACE_BINDING_FILENAME


def test_cli_context_resolves_anchor_project(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    nested = project_root / 'src' / 'pkg'
    nested.mkdir(parents=True)
    (project_root / '.ccb').mkdir()

    context = CliContextBuilder().build(ParsedConfigValidateCommand(project=None), cwd=nested)
    assert context.project.project_root == project_root.resolve()
    assert context.project.source == 'anchor'
    assert context.paths.config_path == project_root.resolve() / '.ccb' / 'ccb.config'


def test_cli_context_resolves_workspace_binding(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    workspace = tmp_path / 'ws' / 'agent1'
    workspace.mkdir(parents=True)
    (project_root / '.ccb').mkdir(parents=True)
    (workspace / WORKSPACE_BINDING_FILENAME).write_text(
        json.dumps({'target_project': str(project_root)}),
        encoding='utf-8',
    )

    context = CliContextBuilder().build(ParsedConfigValidateCommand(project=None), cwd=workspace)
    assert context.project.project_root == project_root.resolve()
    assert context.project.source == 'workspace-binding'


def test_cli_context_uses_explicit_project_over_cwd(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    (project_root / '.ccb').mkdir(parents=True)

    context = CliContextBuilder().build(
        ParsedConfigValidateCommand(project=str(project_root)),
        cwd=elsewhere,
    )
    assert context.cwd == elsewhere
    assert context.project.project_root == project_root.resolve()
    assert context.project.source == 'explicit'


def test_cli_context_bootstraps_missing_project_when_requested(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()

    context = CliContextBuilder().build(
        ParsedStartCommand(project=None, agent_names=(), restore=False, auto_permission=False),
        cwd=project_root,
        bootstrap_if_missing=True,
    )
    assert context.project.project_root == project_root.resolve()
    assert context.project.source == 'bootstrapped'
    assert (project_root / '.ccb').is_dir()
    assert (project_root / '.ccb' / 'ccb.config').is_file()


def test_cli_context_bootstrap_rejects_nested_project_under_parent_anchor(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    nested = project_root / 'nested'
    elsewhere = tmp_path / 'elsewhere'
    nested.mkdir(parents=True)
    elsewhere.mkdir()
    (project_root / '.ccb').mkdir()

    with pytest.raises(ValueError, match='auto-create blocked'):
        CliContextBuilder().build(
            ParsedStartCommand(project=str(nested), agent_names=(), restore=False, auto_permission=False),
            cwd=elsewhere,
            bootstrap_if_missing=True,
        )


def test_cli_context_bootstrap_rejects_parent_anchor_from_current_directory(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    nested = project_root / 'nested'
    nested.mkdir(parents=True)
    (project_root / '.ccb').mkdir()

    with pytest.raises(ValueError, match='auto-create blocked'):
        CliContextBuilder().build(
            ParsedStartCommand(project=None, agent_names=(), restore=False, auto_permission=False),
            cwd=nested,
            bootstrap_if_missing=True,
        )


def test_cli_context_bootstraps_local_project_instead_of_reusing_home_anchor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / 'home'
    project_root = home / 'work' / 'repo'
    home.mkdir()
    project_root.mkdir(parents=True)
    (home / '.ccb').mkdir()
    monkeypatch.setenv('HOME', str(home))

    context = CliContextBuilder().build(
        ParsedStartCommand(project=None, agent_names=(), restore=False, auto_permission=False),
        cwd=project_root,
        bootstrap_if_missing=True,
    )
    assert context.project.project_root == project_root.resolve()
    assert context.project.source == 'bootstrapped'
    rendered = (project_root / '.ccb' / 'ccb.config').read_text(encoding='utf-8')
    assert rendered == 'cmd, agent1:codex; agent2:codex, agent3:claude\n'
