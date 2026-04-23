from __future__ import annotations

import subprocess
from pathlib import Path

from ccbd.services.project_namespace_runtime.backend import (
    create_session,
    ensure_server_policy,
    list_windows,
    prepare_server,
)


class _FlakyBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self._remaining_failures: dict[tuple[str, ...], int] = {}
        self.session_created = False
        self.require_session_for_server_policy = False

    def fail_once(self, *args: str) -> None:
        self._remaining_failures[tuple(args)] = 1

    def _tmux_run(self, args, *, check=False, capture=False, timeout=None):
        del check, capture, timeout
        key = tuple(str(item) for item in args)
        self.calls.append(key)
        if key[:1] == ('new-session',):
            self.session_created = True
        remaining = int(self._remaining_failures.get(key, 0))
        if remaining > 0:
            self._remaining_failures[key] = remaining - 1
            return subprocess.CompletedProcess(
                ['tmux', *key],
                1,
                stdout='',
                stderr='no server running on /tmp/ccb-runtime/test.sock\n',
            )
        if key == ('set-option', '-g', 'destroy-unattached', 'off') and self.require_session_for_server_policy and not self.session_created:
            return subprocess.CompletedProcess(
                ['tmux', *key],
                1,
                stdout='',
                stderr='no server running on /tmp/ccb-runtime/test.sock\n',
            )
        if key[:1] == ('list-windows',):
            return subprocess.CompletedProcess(
                ['tmux', *key],
                0,
                stdout='@1\tcmd\t1\n@2\tworkspace\t0\n',
                stderr='',
            )
        return subprocess.CompletedProcess(['tmux', *key], 0, stdout='', stderr='')


def test_prepare_server_then_create_session_and_server_policy_retry_transient_tmux_failures(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('CCB_TMUX_OBJECT_READY_POLL_INTERVAL_S', '0')
    backend = _FlakyBackend()
    backend.fail_once('start-server')
    backend.fail_once('set-option', '-g', 'destroy-unattached', 'off')
    backend.fail_once(
        'new-session',
        '-d',
        '-x',
        '160',
        '-y',
        '48',
        '-s',
        'ccb-proj',
        '-n',
        'cmd',
        '-c',
        str(tmp_path),
        'sh',
        '-lc',
        'while :; do sleep 3600; done',
    )

    prepare_server(backend)
    create_session(backend, session_name='ccb-proj', project_root=tmp_path, window_name='cmd')
    ensure_server_policy(backend)

    assert backend.calls.count(('start-server',)) == 2
    assert backend.calls.count(('set-option', '-g', 'destroy-unattached', 'off')) == 2
    assert backend.calls.count(
        (
            'new-session',
            '-d',
            '-x',
            '160',
            '-y',
            '48',
            '-s',
            'ccb-proj',
            '-n',
            'cmd',
            '-c',
            str(tmp_path),
            'sh',
            '-lc',
            'while :; do sleep 3600; done',
        )
    ) == 2


def test_prepare_server_does_not_require_server_policy_before_session_exists(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('CCB_TMUX_OBJECT_READY_POLL_INTERVAL_S', '0')
    backend = _FlakyBackend()
    backend.require_session_for_server_policy = True

    prepare_server(backend)
    create_session(backend, session_name='ccb-proj', project_root=tmp_path, window_name='cmd')
    ensure_server_policy(backend)

    assert backend.calls[0] == ('start-server',)
    assert ('set-option', '-g', 'destroy-unattached', 'off') not in backend.calls[:2]
    assert backend.calls[-1] == ('set-option', '-g', 'destroy-unattached', 'off')


def test_list_windows_retries_transient_tmux_failures(monkeypatch) -> None:
    monkeypatch.setenv('CCB_TMUX_OBJECT_READY_POLL_INTERVAL_S', '0')
    backend = _FlakyBackend()
    backend.fail_once('list-windows', '-t', 'ccb-proj', '-F', '#{window_id}\t#{window_name}\t#{window_active}')

    windows = list_windows(backend, 'ccb-proj')

    assert [(window.window_id, window.window_name, window.active) for window in windows] == [
        ('@1', 'cmd', True),
        ('@2', 'workspace', False),
    ]
    assert backend.calls.count(('list-windows', '-t', 'ccb-proj', '-F', '#{window_id}\t#{window_name}\t#{window_active}')) == 2
