from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace

from agents.models import AgentSpec, PermissionMode, QueuePolicy, RestoreMode, RuntimeMode, WorkspaceMode
from agents.store import AgentSpecStore
from ccbd.socket_client import CcbdClient
from ccbd.lifecycle_report_store import CcbdStartupReportStore
from ccbd.models import CcbdStartupReport
import cli.services.start_runtime as start_runtime_module
from cli.context import CliContextBuilder
from cli.models import ParsedStartCommand
from cli.services.start import start_agents
from project.resolver import bootstrap_project
from storage.paths import PathLayout
from workspace.materializer import WorkspaceMaterializer
from workspace.planner import WorkspacePlanner
import pytest


def _init_git_repo(project_root: Path) -> None:
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / 'README.md').write_text('hello\n', encoding='utf-8')
    subprocess.run(['git', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=project_root, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=project_root, check=True)
    subprocess.run(['git', 'add', '.'], cwd=project_root, check=True)
    subprocess.run(['git', 'commit', '-m', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _worktree_spec(name: str = 'agent1') -> AgentSpec:
    return AgentSpec(
        name=name,
        provider='codex',
        target='.',
        workspace_mode=WorkspaceMode.GIT_WORKTREE,
        workspace_root=None,
        runtime_mode=RuntimeMode.PANE_BACKED,
        restore_default=RestoreMode.AUTO,
        permission_default=PermissionMode.MANUAL,
        queue_policy=QueuePolicy.SERIAL_PER_AGENT,
    )


def test_start_agents_calls_ccbd_start_with_cli_flags(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-start-thin-client'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedStartCommand(project=None, agent_names=('demo',), restore=True, auto_permission=True)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    seen: dict[str, object] = {}

    class _FakeClient:
        def start(self, **kwargs):
            seen.update(kwargs)
            return {
                'project_root': str(project_root),
                'project_id': context.project.project_id,
                'started': ['demo'],
                'socket_path': str(context.paths.ccbd_socket_path),
                'cleanup_summaries': [],
            }

    monkeypatch.setattr(
        'cli.services.start.ensure_daemon_started',
        lambda context: SimpleNamespace(client=_FakeClient(), started=True),
    )

    summary = start_agents(context, command)

    assert seen == {
        'agent_names': ('demo',),
        'restore': True,
        'auto_permission': True,
    }
    assert summary.project_root == str(project_root)
    assert summary.project_id == context.project.project_id
    assert summary.started == ('demo',)
    assert summary.daemon_started is True
    assert summary.socket_path == str(context.paths.ccbd_socket_path)


def test_start_agents_parses_cleanup_summaries_from_ccbd_payload(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-start-cleanup'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedStartCommand(project=None, agent_names=(), restore=False, auto_permission=False)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    class _FakeClient:
        def start(self, **kwargs):
            del kwargs
            return {
                'project_root': str(project_root),
                'project_id': context.project.project_id,
                'started': ['demo'],
                'socket_path': str(context.paths.ccbd_socket_path),
                'cleanup_summaries': [
                    {
                        'socket_name': 'sock-a',
                        'owned_panes': ['%44'],
                        'active_panes': ['%44'],
                        'orphaned_panes': [],
                        'killed_panes': [],
                    },
                ],
            }

    monkeypatch.setattr(
        'cli.services.start.ensure_daemon_started',
        lambda context: SimpleNamespace(client=_FakeClient(), started=False),
    )

    summary = start_agents(context, command)

    assert summary.daemon_started is False
    assert len(summary.cleanup_summaries) == 1
    assert summary.cleanup_summaries[0].socket_name == 'sock-a'
    assert summary.cleanup_summaries[0].owned_panes == ('%44',)


def test_start_agents_updates_startup_report_with_daemon_started_flag(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-start-report'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedStartCommand(project=None, agent_names=('demo',), restore=False, auto_permission=False)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)
    CcbdStartupReportStore(context.paths).save(
        CcbdStartupReport(
            project_id=context.project.project_id,
            generated_at='2026-04-03T00:00:00Z',
            trigger='start_command',
            status='ok',
            requested_agents=('demo',),
            desired_agents=('demo',),
            restore_requested=False,
            auto_permission=False,
            daemon_generation=1,
            daemon_started=None,
            config_signature='sig-1',
            inspection={},
            restore_summary={},
            actions_taken=('launch_runtime:demo',),
            cleanup_summaries=(),
            agent_results=(),
            failure_reason=None,
        )
    )

    class _FakeClient:
        def start(self, **kwargs):
            del kwargs
            return {
                'project_root': str(project_root),
                'project_id': context.project.project_id,
                'started': ['demo'],
                'socket_path': str(context.paths.ccbd_socket_path),
                'cleanup_summaries': [],
            }

    monkeypatch.setattr(
        'cli.services.start.ensure_daemon_started',
        lambda context: SimpleNamespace(client=_FakeClient(), started=True),
    )

    start_agents(context, command)

    report = CcbdStartupReportStore(context.paths).load()
    assert report is not None
    assert report.daemon_started is True


def test_start_agents_validates_config_before_starting_daemon(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-start-invalid-config'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('agent1:codex, cmd\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedStartCommand(project=None, agent_names=(), restore=False, auto_permission=False)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)
    daemon_calls: list[str] = []

    monkeypatch.setattr(
        'cli.services.start.ensure_daemon_started',
        lambda context: daemon_calls.append(str(context.project.project_root)) or SimpleNamespace(client=None, started=False),
    )

    with pytest.raises(Exception, match='layout_spec must anchor cmd as the first pane'):
        start_agents(context, command)

    assert daemon_calls == []


def test_start_agents_retires_removed_merged_worktree_before_start(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-start-retire-worktree'
    _init_git_repo(project_root)
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)

    spec = _worktree_spec('agent1')
    layout = PathLayout(project_root)
    AgentSpecStore(layout).save(spec)
    plan = WorkspacePlanner().plan(spec, bootstrap_project(project_root))
    WorkspaceMaterializer().materialize(plan)

    command = ParsedStartCommand(project=None, agent_names=(), restore=True, auto_permission=True)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    class _FakeClient:
        def start(self, **kwargs):
            del kwargs
            return {
                'project_root': str(project_root),
                'project_id': context.project.project_id,
                'started': ['demo'],
                'socket_path': str(context.paths.ccbd_socket_path),
                'cleanup_summaries': [],
            }

    monkeypatch.setattr(
        'cli.services.start.ensure_daemon_started',
        lambda context: SimpleNamespace(client=_FakeClient(), started=False),
    )

    summary = start_agents(context, command)

    assert summary.started == ('demo',)
    assert len(summary.worktree_retired) == 1
    assert summary.worktree_retired[0].agent_name == 'agent1'
    assert plan.workspace_path.exists() is False
    assert context.paths.agent_dir('agent1').exists() is False
    worktrees = subprocess.run(
        ['git', '-C', str(project_root), 'worktree', 'list', '--porcelain'],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout
    assert str(plan.workspace_path) not in worktrees


def test_start_agents_blocks_removed_unmerged_worktree_before_start(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-start-block-worktree'
    _init_git_repo(project_root)
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)

    spec = _worktree_spec('agent1')
    layout = PathLayout(project_root)
    AgentSpecStore(layout).save(spec)
    plan = WorkspacePlanner().plan(spec, bootstrap_project(project_root))
    WorkspaceMaterializer().materialize(plan)
    (plan.workspace_path / 'feature.txt').write_text('worktree-only\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(plan.workspace_path), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(plan.workspace_path), 'commit', '-m', 'worktree'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    command = ParsedStartCommand(project=None, agent_names=(), restore=True, auto_permission=True)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)
    seen: dict[str, object] = {}

    class _FakeClient:
        def start(self, **kwargs):
            seen['called'] = kwargs
            return {}

    monkeypatch.setattr(
        'cli.services.start.ensure_daemon_started',
        lambda context: SimpleNamespace(client=_FakeClient(), started=False),
    )

    with pytest.raises(RuntimeError, match='worktree state'):
        start_agents(context, command)

    assert seen == {}
    assert plan.workspace_path.exists() is True


def test_start_agents_reports_active_unmerged_worktree_warning(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-start-warn-worktree'
    _init_git_repo(project_root)
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('agent1:codex(worktree)\n', encoding='utf-8')
    bootstrap_project(project_root)

    spec = _worktree_spec('agent1')
    layout = PathLayout(project_root)
    AgentSpecStore(layout).save(spec)
    plan = WorkspacePlanner().plan(spec, bootstrap_project(project_root))
    WorkspaceMaterializer().materialize(plan)
    (plan.workspace_path / 'feature.txt').write_text('worktree-only\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(plan.workspace_path), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(plan.workspace_path), 'commit', '-m', 'worktree'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    command = ParsedStartCommand(project=None, agent_names=(), restore=True, auto_permission=True)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    class _FakeClient:
        def start(self, **kwargs):
            del kwargs
            return {
                'project_root': str(project_root),
                'project_id': context.project.project_id,
                'started': ['agent1'],
                'socket_path': str(context.paths.ccbd_socket_path),
                'cleanup_summaries': [],
            }

    monkeypatch.setattr(
        'cli.services.start.ensure_daemon_started',
        lambda context: SimpleNamespace(client=_FakeClient(), started=False),
    )

    summary = start_agents(context, command)

    assert len(summary.worktree_warnings) == 1
    assert summary.worktree_warnings[0].agent_name == 'agent1'
    assert summary.worktree_warnings[0].merged is False


def test_start_request_client_upgrades_short_ccbd_timeout(tmp_path: Path) -> None:
    client = CcbdClient(tmp_path / 'ccbd.sock', timeout_s=0.2, ipc_kind='named_pipe')

    upgraded = start_runtime_module._start_request_client(client)

    assert isinstance(upgraded, CcbdClient)
    assert upgraded is not client
    assert upgraded._socket_path == client._socket_path
    assert upgraded._ipc_kind == 'named_pipe'
    assert upgraded._timeout_s >= 15.0


def test_start_request_client_keeps_non_ccbd_clients_untouched() -> None:
    client = object()

    assert start_runtime_module._start_request_client(client) is client
