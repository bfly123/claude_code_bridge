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


class _FakeAttachProcess:
    def __init__(self, *, pid: int, returncode: int | None = None):
        self.pid = pid
        self.returncode = returncode
        self.wait_calls = 0

    def poll(self):
        return self.returncode

    def wait(self):
        self.wait_calls += 1
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


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

    run_calls: list[list[str]] = []
    attach_calls: list[list[str]] = []
    attach_process = _FakeAttachProcess(pid=4242, returncode=0)

    def _run(args, **kwargs):
        call = list(args)
        run_calls.append(call)
        if call[3:4] == ['list-clients']:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout='4242\n')
        return subprocess.CompletedProcess(args=args, returncode=0)

    def _popen(args, **kwargs):
        del kwargs
        attach_calls.append(list(args))
        return attach_process

    monkeypatch.setattr('cli.services.start_foreground.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.start_foreground.CcbdClient', _FakeClient)
    monkeypatch.setattr('cli.services.start_foreground.subprocess.run', _run)
    monkeypatch.setattr('cli.services.start_foreground.subprocess.Popen', _popen)

    summary = attach_started_project_namespace(context)

    assert summary.project_id == context.project.project_id
    assert summary.tmux_socket_path == str(context.paths.ccbd_tmux_socket_path)
    assert summary.tmux_session_name == context.paths.ccbd_tmux_session_name
    assert run_calls == [
        ['tmux', '-S', str(context.paths.ccbd_tmux_socket_path), 'has-session', '-t', context.paths.ccbd_tmux_session_name],
        [
            'tmux',
            '-S',
            str(context.paths.ccbd_tmux_socket_path),
            'select-window',
            '-t',
            f'{context.paths.ccbd_tmux_session_name}:{context.paths.ccbd_tmux_workspace_window_name}',
        ],
        [
            'tmux',
            '-S',
            str(context.paths.ccbd_tmux_socket_path),
            'list-clients',
            '-t',
            context.paths.ccbd_tmux_session_name,
            '-F',
            '#{client_pid}',
        ],
    ]
    assert attach_calls == [
        ['tmux', '-S', str(context.paths.ccbd_tmux_socket_path), 'attach-session', '-t', context.paths.ccbd_tmux_session_name]
    ]


def test_start_foreground_waits_for_workspace_window_visibility_before_attach(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-attach-delayed-window'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    context = _context(project_root)

    class _FakeClient:
        def __init__(self, socket_path):
            self.socket_path = socket_path
            self.calls = 0

        def ping(self, target: str) -> dict[str, object]:
            assert target == 'ccbd'
            self.calls += 1
            return {
                'namespace_tmux_socket_path': str(context.paths.ccbd_tmux_socket_path),
                'namespace_tmux_session_name': context.paths.ccbd_tmux_session_name,
                'namespace_workspace_window_name': context.paths.ccbd_tmux_workspace_window_name,
                'namespace_ui_attachable': True,
            }

    run_calls: list[list[str]] = []
    attach_calls: list[list[str]] = []
    attach_process = _FakeAttachProcess(pid=4343, returncode=0)
    select_attempts = 0

    def _run(args, **kwargs):
        nonlocal select_attempts
        call = list(args)
        run_calls.append(call)
        if call[3:4] == ['list-clients']:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout='4343\n')
        if call[3:4] == ['select-window']:
            select_attempts += 1
            return subprocess.CompletedProcess(args=args, returncode=0 if select_attempts >= 2 else 1)
        return subprocess.CompletedProcess(args=args, returncode=0)

    def _popen(args, **kwargs):
        del kwargs
        attach_calls.append(list(args))
        return attach_process

    monkeypatch.setattr('cli.services.start_foreground.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.start_foreground.CcbdClient', _FakeClient)
    monkeypatch.setattr('cli.services.start_foreground.subprocess.run', _run)
    monkeypatch.setattr('cli.services.start_foreground.subprocess.Popen', _popen)
    monkeypatch.setattr('cli.services.start_foreground._ATTACH_TARGET_READY_POLL_INTERVAL_S', 0.0)

    summary = attach_started_project_namespace(context)

    assert summary.project_id == context.project.project_id
    assert run_calls == [
        ['tmux', '-S', str(context.paths.ccbd_tmux_socket_path), 'has-session', '-t', context.paths.ccbd_tmux_session_name],
        [
            'tmux',
            '-S',
            str(context.paths.ccbd_tmux_socket_path),
            'select-window',
            '-t',
            f'{context.paths.ccbd_tmux_session_name}:{context.paths.ccbd_tmux_workspace_window_name}',
        ],
        ['tmux', '-S', str(context.paths.ccbd_tmux_socket_path), 'has-session', '-t', context.paths.ccbd_tmux_session_name],
        [
            'tmux',
            '-S',
            str(context.paths.ccbd_tmux_socket_path),
            'select-window',
            '-t',
            f'{context.paths.ccbd_tmux_session_name}:{context.paths.ccbd_tmux_workspace_window_name}',
        ],
        [
            'tmux',
            '-S',
            str(context.paths.ccbd_tmux_socket_path),
            'list-clients',
            '-t',
            context.paths.ccbd_tmux_session_name,
            '-F',
            '#{client_pid}',
        ],
    ]
    assert attach_calls == [
        ['tmux', '-S', str(context.paths.ccbd_tmux_socket_path), 'attach-session', '-t', context.paths.ccbd_tmux_session_name]
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

    run_calls: list[list[str]] = []
    attach_calls: list[list[str]] = []
    attach_process = _FakeAttachProcess(pid=5151, returncode=1)

    def _run(args, **kwargs):
        del kwargs
        call = list(args)
        run_calls.append(call)
        if len(run_calls) in {1, 2}:
            return subprocess.CompletedProcess(args=args, returncode=0)
        if len(run_calls) == 3:
            return subprocess.CompletedProcess(args=args, returncode=1, stdout='')
        if len(run_calls) == 4:
            return subprocess.CompletedProcess(args=args, returncode=1)
        raise AssertionError(f'unexpected subprocess call: {call}')

    def _popen(args, **kwargs):
        del kwargs
        attach_calls.append(list(args))
        return attach_process

    monkeypatch.setattr('cli.services.start_foreground.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.start_foreground.CcbdClient', _FakeClient)
    monkeypatch.setattr('cli.services.start_foreground.subprocess.run', _run)
    monkeypatch.setattr('cli.services.start_foreground.subprocess.Popen', _popen)

    with pytest.raises(ForegroundAttachError, match='session exited before foreground attach completed'):
        attach_started_project_namespace(context)

    assert run_calls == [
        ['tmux', '-S', str(context.paths.ccbd_tmux_socket_path), 'has-session', '-t', context.paths.ccbd_tmux_session_name],
        [
            'tmux',
            '-S',
            str(context.paths.ccbd_tmux_socket_path),
            'select-window',
            '-t',
            f'{context.paths.ccbd_tmux_session_name}:{context.paths.ccbd_tmux_workspace_window_name}',
        ],
        [
            'tmux',
            '-S',
            str(context.paths.ccbd_tmux_socket_path),
            'list-clients',
            '-t',
            context.paths.ccbd_tmux_session_name,
            '-F',
            '#{client_pid}',
        ],
        ['tmux', '-S', str(context.paths.ccbd_tmux_socket_path), 'has-session', '-t', context.paths.ccbd_tmux_session_name],
    ]
    assert attach_calls == [
        ['tmux', '-S', str(context.paths.ccbd_tmux_socket_path), 'attach-session', '-t', context.paths.ccbd_tmux_session_name]
    ]


def test_start_foreground_treats_post_attach_session_exit_as_success(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-attach-killed-later'
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

    run_calls: list[list[str]] = []
    attach_calls: list[list[str]] = []
    attach_process = _FakeAttachProcess(pid=6161, returncode=None)

    def _run(args, **kwargs):
        call = list(args)
        run_calls.append(call)
        if call[3:4] == ['list-clients']:
            attach_process.returncode = 1
            return subprocess.CompletedProcess(args=args, returncode=0, stdout='6161\n')
        return subprocess.CompletedProcess(args=args, returncode=0)

    def _popen(args, **kwargs):
        del kwargs
        attach_calls.append(list(args))
        return attach_process

    monkeypatch.setattr('cli.services.start_foreground.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.start_foreground.CcbdClient', _FakeClient)
    monkeypatch.setattr('cli.services.start_foreground.subprocess.run', _run)
    monkeypatch.setattr('cli.services.start_foreground.subprocess.Popen', _popen)

    summary = attach_started_project_namespace(context)

    assert summary.project_id == context.project.project_id
    assert attach_process.wait_calls == 1
    assert run_calls == [
        ['tmux', '-S', str(context.paths.ccbd_tmux_socket_path), 'has-session', '-t', context.paths.ccbd_tmux_session_name],
        [
            'tmux',
            '-S',
            str(context.paths.ccbd_tmux_socket_path),
            'select-window',
            '-t',
            f'{context.paths.ccbd_tmux_session_name}:{context.paths.ccbd_tmux_workspace_window_name}',
        ],
        [
            'tmux',
            '-S',
            str(context.paths.ccbd_tmux_socket_path),
            'list-clients',
            '-t',
            context.paths.ccbd_tmux_session_name,
            '-F',
            '#{client_pid}',
        ],
    ]
    assert attach_calls == [
        ['tmux', '-S', str(context.paths.ccbd_tmux_socket_path), 'attach-session', '-t', context.paths.ccbd_tmux_session_name]
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
