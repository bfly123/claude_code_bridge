from __future__ import annotations

import signal

import cli.kill_runtime.processes as processes


def test_kill_pid_tree_once_uses_taskkill_on_windows(monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(processes.os, 'name', 'nt')
    monkeypatch.setattr(processes, '_windows_pid_safe_to_terminate', lambda pid: True)
    monkeypatch.setattr(
        processes.subprocess,
        'run',
        lambda args, capture_output=True: calls.append(list(args)) or None,
    )

    assert processes._kill_pid_tree_once(321, force=True) is True
    assert calls == [["taskkill", "/F", "/T", "/PID", "321"]]


def test_kill_pid_tree_once_prefers_process_group_on_posix(monkeypatch) -> None:
    killed: list[tuple[int, signal.Signals]] = []
    kill_pid_calls: list[tuple[int, bool]] = []

    monkeypatch.setattr(processes.os, 'name', 'posix')
    monkeypatch.setattr(processes, '_safe_getpgid', lambda pid: 900)
    monkeypatch.setattr(processes, '_safe_getpgrp', lambda: 901)
    monkeypatch.setattr(processes.os, 'killpg', lambda pgid, sig: killed.append((pgid, sig)), raising=False)
    monkeypatch.setattr(processes, 'kill_pid', lambda pid, force=False: kill_pid_calls.append((pid, force)) or True)

    assert processes._kill_pid_tree_once(123, force=False) is True
    assert killed == [(900, signal.SIGTERM)]
    assert kill_pid_calls == []


def test_kill_pid_tree_once_skips_untrusted_windows_pid(monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(processes.os, 'name', 'nt')
    monkeypatch.setattr(processes, '_windows_pid_safe_to_terminate', lambda pid: False)
    monkeypatch.setattr(
        processes.subprocess,
        'run',
        lambda args, capture_output=True: calls.append(list(args)) or None,
    )

    assert processes._kill_pid_tree_once(321, force=True) is False
    assert calls == []


def test_windows_pid_safe_to_terminate_allows_current_child(monkeypatch) -> None:
    monkeypatch.setattr(processes.os, 'name', 'nt')
    monkeypatch.setattr(processes.os, 'getpid', lambda: 500)
    monkeypatch.setattr(processes.os, 'getppid', lambda: 400)
    monkeypatch.setattr(processes, '_windows_ancestor_chain', lambda pid, max_depth=32: (900, 500, 400) if pid == 900 else (500, 400))

    assert processes._windows_pid_safe_to_terminate(900) is True


def test_windows_pid_safe_to_terminate_blocks_current_shell_chain(monkeypatch) -> None:
    monkeypatch.setattr(processes.os, 'name', 'nt')
    monkeypatch.setattr(processes.os, 'getpid', lambda: 500)
    monkeypatch.setattr(processes.os, 'getppid', lambda: 400)
    monkeypatch.setattr(processes, '_windows_ancestor_chain', lambda pid, max_depth=32: (pid, 300))

    assert processes._windows_pid_safe_to_terminate(500) is False
    assert processes._windows_pid_safe_to_terminate(400) is False
    assert processes._windows_pid_safe_to_terminate(900) is False
