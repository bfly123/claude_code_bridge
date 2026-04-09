from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from cli.context import CliContextBuilder
from cli.models import ParsedOpenCommand
from cli.services.daemon_runtime import CcbdServiceError
from cli.services.open import open_project
from project.resolver import bootstrap_project


def test_open_project_attaches_to_namespace_tmux_session(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-open'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedOpenCommand(project=None)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    class _FakeClient:
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

    monkeypatch.setattr('cli.services.open.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr(
        'cli.services.open.connect_mounted_daemon',
        lambda context, allow_restart_stale: SimpleNamespace(client=_FakeClient()),
    )
    monkeypatch.setattr('cli.services.open.subprocess.run', _run)

    summary = open_project(context, command)

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


def test_open_project_reports_clean_error_when_session_exits_before_attach(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-open-fail'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedOpenCommand(project=None)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    class _FakeClient:
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
        if len(calls) == 1:
            return subprocess.CompletedProcess(args=args, returncode=0)
        if len(calls) == 2:
            return subprocess.CompletedProcess(args=args, returncode=0)
        if len(calls) == 3:
            return subprocess.CompletedProcess(args=args, returncode=1)
        if len(calls) == 4:
            return subprocess.CompletedProcess(args=args, returncode=1)
        raise AssertionError(f'unexpected subprocess call: {call}')

    monkeypatch.setattr('cli.services.open.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr(
        'cli.services.open.connect_mounted_daemon',
        lambda context, allow_restart_stale: SimpleNamespace(client=_FakeClient()),
    )
    monkeypatch.setattr('cli.services.open.subprocess.run', _run)

    with pytest.raises(RuntimeError, match='session exited before attach completed'):
        open_project(context, command)

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


def test_open_project_waits_for_config_drift_recovery_before_attach(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-open-config-drift'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedOpenCommand(project=None)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    class _FakeClient:
        def ping(self, target: str) -> dict[str, object]:
            assert target == 'ccbd'
            return {
                'namespace_tmux_socket_path': str(context.paths.ccbd_tmux_socket_path),
                'namespace_tmux_session_name': context.paths.ccbd_tmux_session_name,
                'namespace_workspace_window_name': context.paths.ccbd_tmux_workspace_window_name,
                'namespace_ui_attachable': True,
            }

    outcomes = iter(
        (
            CcbdServiceError('mounted ccbd config does not match current .ccb/ccb.config'),
            CcbdServiceError('project ccbd is unmounted; run `ccb [agents...]` first'),
            SimpleNamespace(client=_FakeClient()),
        )
    )

    def _connect(context, allow_restart_stale):
        del context, allow_restart_stale
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    calls: list[list[str]] = []

    def _run(args, **kwargs):
        del kwargs
        calls.append(list(args))
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr('cli.services.open.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.open.connect_mounted_daemon', _connect)
    monkeypatch.setattr('cli.services.open.subprocess.run', _run)
    monkeypatch.setattr('cli.services.open.time.sleep', lambda seconds: None)

    summary = open_project(context, command)

    assert summary.project_id == context.project.project_id
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
