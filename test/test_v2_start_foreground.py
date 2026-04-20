from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from cli.context import CliContextBuilder
from cli.models import ParsedStartCommand
from cli.services.start_foreground import ForegroundAttachError, attach_started_project_namespace
from project.resolver import bootstrap_project


def _context(project_root: Path):
    command = ParsedStartCommand(project=None, agent_names=(), restore=True, auto_permission=True)
    return CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)


def test_start_foreground_attaches_to_namespace_tmux_session(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-attach'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    context = _context(project_root)

    class _FakeClient:
        def __init__(self, socket_path):
            self.socket_path = socket_path

        def ping(self, target: str) -> dict[str, object]:
            assert target == 'ccbd'
            return {
                'namespace_tmux_socket_path': str(context.paths.ccbd_tmux_socket_path),
                'namespace_tmux_session_name': context.paths.ccbd_tmux_session_name,
                'namespace_workspace_window_name': context.paths.ccbd_tmux_workspace_window_name,
                'namespace_ui_attachable': True,
            }

    calls: list[list[str]] = []

    def _run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr('cli.services.start_foreground.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.start_foreground.CcbdClient', _FakeClient)
    monkeypatch.setattr('cli.services.start_foreground.subprocess.run', _run)

    summary = attach_started_project_namespace(context)

    assert summary.project_id == context.project.project_id
    assert summary.tmux_socket_path == str(context.paths.ccbd_tmux_socket_path)
    assert summary.tmux_session_name == context.paths.ccbd_tmux_session_name
    assert calls == [
        ['tmux', '-S', str(context.paths.ccbd_tmux_socket_path), 'has-session', '-t', context.paths.ccbd_tmux_session_name],
        [
            'tmux',
            '-S',
            str(context.paths.ccbd_tmux_socket_path),
            'select-window',
            '-t',
            f'{context.paths.ccbd_tmux_session_name}:{context.paths.ccbd_tmux_workspace_window_name}',
        ],
        ['tmux', '-S', str(context.paths.ccbd_tmux_socket_path), 'attach-session', '-t', context.paths.ccbd_tmux_session_name],
    ]


def test_start_foreground_reports_clean_error_when_session_exits_before_attach(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-attach-fail'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    context = _context(project_root)

    class _FakeClient:
        def __init__(self, socket_path):
            self.socket_path = socket_path

        def ping(self, target: str) -> dict[str, object]:
            assert target == 'ccbd'
            return {
                'namespace_tmux_socket_path': str(context.paths.ccbd_tmux_socket_path),
                'namespace_tmux_session_name': context.paths.ccbd_tmux_session_name,
                'namespace_workspace_window_name': context.paths.ccbd_tmux_workspace_window_name,
                'namespace_ui_attachable': True,
            }

    calls: list[list[str]] = []

    def _run(args, **kwargs):
        del kwargs
        call = list(args)
        calls.append(call)
        if len(calls) in {1, 2}:
            return subprocess.CompletedProcess(args=args, returncode=0)
        if len(calls) in {3, 4}:
            return subprocess.CompletedProcess(args=args, returncode=1)
        raise AssertionError(f'unexpected subprocess call: {call}')

    monkeypatch.setattr('cli.services.start_foreground.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.start_foreground.CcbdClient', _FakeClient)
    monkeypatch.setattr('cli.services.start_foreground.subprocess.run', _run)

    with pytest.raises(ForegroundAttachError, match='session exited before foreground attach completed'):
        attach_started_project_namespace(context)

    assert calls == [
        ['tmux', '-S', str(context.paths.ccbd_tmux_socket_path), 'has-session', '-t', context.paths.ccbd_tmux_session_name],
        [
            'tmux',
            '-S',
            str(context.paths.ccbd_tmux_socket_path),
            'select-window',
            '-t',
            f'{context.paths.ccbd_tmux_session_name}:{context.paths.ccbd_tmux_workspace_window_name}',
        ],
        ['tmux', '-S', str(context.paths.ccbd_tmux_socket_path), 'attach-session', '-t', context.paths.ccbd_tmux_session_name],
        ['tmux', '-S', str(context.paths.ccbd_tmux_socket_path), 'has-session', '-t', context.paths.ccbd_tmux_session_name],
    ]


def test_start_foreground_requires_attachable_namespace(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-not-attachable'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    context = _context(project_root)

    class _FakeClient:
        def __init__(self, socket_path):
            self.socket_path = socket_path

        def ping(self, target: str) -> dict[str, object]:
            assert target == 'ccbd'
            return {
                'namespace_tmux_socket_path': str(context.paths.ccbd_tmux_socket_path),
                'namespace_tmux_session_name': context.paths.ccbd_tmux_session_name,
                'namespace_workspace_window_name': context.paths.ccbd_tmux_workspace_window_name,
                'namespace_ui_attachable': False,
            }

    monkeypatch.setattr('cli.services.start_foreground.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.start_foreground.CcbdClient', _FakeClient)

    with pytest.raises(ForegroundAttachError, match='not attachable after successful `ccb` start'):
        attach_started_project_namespace(context)
