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


def test_open_project_named_pipe_recovery_ignores_keyboard_interrupt_noise(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-open-config-drift-named-pipe'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    monkeypatch.setenv('CCB_EXPERIMENTAL_WINDOWS_NATIVE', '1')
    monkeypatch.setenv('CCB_IPC_KIND', 'named_pipe')
    bootstrap_project(project_root)
    command = ParsedOpenCommand(project=None)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    class _FakeClient:
        def ping(self, target: str) -> dict[str, object]:
            assert target == 'ccbd'
            return {
                'namespace_backend_impl': 'psmux',
                'namespace_backend_ref': r'\\.\pipe\psmux-demo',
                'namespace_session_name': 'ccb-repo',
                'namespace_workspace_name': 'workspace',
                'namespace_ui_attachable': True,
            }

    class _FakeBackend:
        def session_exists(self, session_name: str) -> bool:
            assert session_name == 'ccb-repo'
            return True

        def select_window(self, target: str) -> bool:
            assert target == 'ccb-repo:workspace'
            return True

        def attach_session(self, session_name: str, *, env: dict[str, str] | None = None) -> int:
            assert session_name == 'ccb-repo'
            assert env is not None
            return 0

    outcomes = iter(
        (
            CcbdServiceError('mounted ccbd config does not match current .ccb/ccb.config'),
            CcbdServiceError('project ccbd is unmounted; run `ccb [agents...]` first'),
            SimpleNamespace(client=_FakeClient()),
        )
    )
    sleep_calls: list[float] = []

    def _connect(current_context, allow_restart_stale):
        assert current_context is context
        assert allow_restart_stale is False
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def _sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        if len(sleep_calls) == 1:
            raise KeyboardInterrupt

    monkeypatch.setattr('cli.services.open.connect_mounted_daemon', _connect)
    monkeypatch.setattr('cli.services.open.build_mux_backend', lambda **kwargs: _FakeBackend())
    monkeypatch.setattr('cli.services.open.time.sleep', _sleep)

    summary = open_project(context, command)

    assert summary.project_id == context.project.project_id
    assert summary.tmux_socket_path == r'\\.\pipe\psmux-demo'
    assert summary.tmux_session_name == 'ccb-repo'
    assert sleep_calls


def test_open_project_non_named_pipe_recovery_still_propagates_keyboard_interrupt(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-open-config-drift-unix'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedOpenCommand(project=None)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    outcomes = iter(
        (
            CcbdServiceError('mounted ccbd config does not match current .ccb/ccb.config'),
            CcbdServiceError('project ccbd is unmounted; run `ccb [agents...]` first'),
        )
    )

    def _connect(current_context, allow_restart_stale):
        assert current_context is context
        assert allow_restart_stale is False
        raise next(outcomes)

    monkeypatch.setattr('cli.services.open.connect_mounted_daemon', _connect)
    monkeypatch.setattr('cli.services.open.time.sleep', lambda seconds: (_ for _ in ()).throw(KeyboardInterrupt()))

    with pytest.raises(KeyboardInterrupt):
        open_project(context, command)


def test_open_project_named_pipe_recovery_ignores_keyboard_interrupt_during_deadline_checks(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-open-config-drift-monotonic'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    monkeypatch.setenv('CCB_EXPERIMENTAL_WINDOWS_NATIVE', '1')
    monkeypatch.setenv('CCB_IPC_KIND', 'named_pipe')
    bootstrap_project(project_root)
    command = ParsedOpenCommand(project=None)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    class _FakeClient:
        def ping(self, target: str) -> dict[str, object]:
            assert target == 'ccbd'
            return {
                'namespace_backend_impl': 'psmux',
                'namespace_backend_ref': r'\\.\pipe\psmux-demo',
                'namespace_session_name': 'ccb-repo',
                'namespace_workspace_name': 'workspace',
                'namespace_ui_attachable': True,
            }

    class _FakeBackend:
        def session_exists(self, session_name: str) -> bool:
            assert session_name == 'ccb-repo'
            return True

        def select_window(self, target: str) -> bool:
            assert target == 'ccb-repo:workspace'
            return True

        def attach_session(self, session_name: str, *, env: dict[str, str] | None = None) -> int:
            assert session_name == 'ccb-repo'
            assert env is not None
            return 0

    outcomes = iter(
        (
            CcbdServiceError('mounted ccbd config does not match current .ccb/ccb.config'),
            CcbdServiceError('project ccbd is unmounted; run `ccb [agents...]` first'),
            SimpleNamespace(client=_FakeClient()),
        )
    )
    original_monotonic = __import__('time').monotonic
    monotonic_calls = {'count': 0}

    def _connect(current_context, allow_restart_stale):
        assert current_context is context
        assert allow_restart_stale is False
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def _monotonic() -> float:
        monotonic_calls['count'] += 1
        if monotonic_calls['count'] == 1:
            raise KeyboardInterrupt
        return original_monotonic()

    monkeypatch.setattr('cli.services.open.connect_mounted_daemon', _connect)
    monkeypatch.setattr('cli.services.open.build_mux_backend', lambda **kwargs: _FakeBackend())
    monkeypatch.setattr('cli.services.open.time.sleep', lambda seconds: None)
    monkeypatch.setattr('cli.services.open.time.monotonic', _monotonic)

    summary = open_project(context, command)

    assert summary.tmux_session_name == 'ccb-repo'
    assert monotonic_calls['count'] >= 2


def test_open_project_uses_backend_generic_namespace_fields_for_psmux(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-open-psmux'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    bootstrap_project(project_root)
    command = ParsedOpenCommand(project=None)
    context = CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)

    class _FakeClient:
        def ping(self, target: str) -> dict[str, object]:
            assert target == 'ccbd'
            return {
                'namespace_backend_impl': 'psmux',
                'namespace_backend_ref': r'\\.\pipe\psmux-demo',
                'namespace_session_name': 'ccb-repo',
                'namespace_workspace_name': 'workspace',
                'namespace_ui_attachable': True,
            }

    class _FakeBackend:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        def session_exists(self, session_name: str) -> bool:
            self.calls.append(('session_exists', session_name))
            return True

        def select_window(self, target: str) -> bool:
            self.calls.append(('select_window', target))
            return True

        def attach_session(self, session_name: str, *, env: dict[str, str] | None = None) -> int:
            self.calls.append(('attach_session', session_name))
            assert env is not None
            assert 'TMUX' not in env
            assert 'TMUX_PANE' not in env
            return 0

    backend = _FakeBackend()
    build_calls: list[tuple[str | None, str | None]] = []

    def _build_mux_backend(*, backend_impl: str | None = None, socket_name: str | None = None, socket_path: str | None = None):
        del socket_name
        build_calls.append((backend_impl, socket_path))
        return backend

    monkeypatch.setattr(
        'cli.services.open.connect_mounted_daemon',
        lambda context, allow_restart_stale: SimpleNamespace(client=_FakeClient()),
    )
    monkeypatch.setattr('cli.services.open.build_mux_backend', _build_mux_backend)
    monkeypatch.setattr(
        'cli.services.open.subprocess.run',
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('tmux subprocess should not run for psmux open')),
    )

    summary = open_project(context, command)

    assert summary.project_id == context.project.project_id
    assert summary.tmux_socket_path == r'\\.\pipe\psmux-demo'
    assert summary.tmux_session_name == 'ccb-repo'
    assert build_calls == [('psmux', r'\\.\pipe\psmux-demo')]
    assert backend.calls == [
        ('session_exists', 'ccb-repo'),
        ('select_window', 'ccb-repo:workspace'),
        ('attach_session', 'ccb-repo'),
    ]
