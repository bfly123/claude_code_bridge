from __future__ import annotations

from pathlib import Path
import time
from types import SimpleNamespace

import pytest

from cli.services.daemon_runtime import keeper as keeper_runtime


def test_spawn_keeper_process_uses_lib_root_keeper_main(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo'
    ccbd_dir = project_root / '.ccb' / 'ccbd'
    context = SimpleNamespace(
        project=SimpleNamespace(project_root=project_root),
        paths=SimpleNamespace(ccbd_dir=ccbd_dir),
    )
    popen_calls: list[dict[str, object]] = []

    class _FakePopen:
        def __init__(self, cmd, **kwargs) -> None:
            popen_calls.append({'cmd': cmd, **kwargs})

    monkeypatch.setattr(keeper_runtime.subprocess, 'Popen', _FakePopen)

    keeper_runtime.spawn_keeper_process(context)

    assert len(popen_calls) == 1
    call = popen_calls[0]
    expected_script = Path(keeper_runtime.__file__).resolve().parents[3] / 'ccbd' / 'keeper_main.py'
    assert call['cmd'][1] == str(expected_script)
    assert str(expected_script.parent.parent) in str(call['env']['PYTHONPATH'])


def test_wait_for_keeper_ready_named_pipe_ignores_keyboard_interrupt_noise(monkeypatch) -> None:
    context = SimpleNamespace(paths=SimpleNamespace(ccbd_ipc_kind='named_pipe'))
    states = iter((SimpleNamespace(keeper_pid=0), SimpleNamespace(keeper_pid=123)))
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        keeper_runtime,
        'KeeperStateStore',
        lambda paths: SimpleNamespace(load=lambda: next(states)),
    )
    monkeypatch.setattr(
        keeper_runtime,
        'keeper_state_is_running',
        lambda state, process_exists_fn=None: bool(getattr(state, 'keeper_pid', 0)),
    )

    def _sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        if len(sleep_calls) == 1:
            raise KeyboardInterrupt

    monkeypatch.setattr(keeper_runtime.time, 'sleep', _sleep)

    assert keeper_runtime.wait_for_keeper_ready(context, timeout_s=0.2) is True
    assert sleep_calls


def test_wait_for_keeper_ready_non_named_pipe_still_propagates_keyboard_interrupt(monkeypatch) -> None:
    context = SimpleNamespace(paths=SimpleNamespace(ccbd_ipc_kind='unix_socket'))

    monkeypatch.setattr(
        keeper_runtime,
        'KeeperStateStore',
        lambda paths: SimpleNamespace(load=lambda: SimpleNamespace(keeper_pid=0)),
    )
    monkeypatch.setattr(
        keeper_runtime,
        'keeper_state_is_running',
        lambda state, process_exists_fn=None: False,
    )
    monkeypatch.setattr(
        keeper_runtime.time,
        'sleep',
        lambda seconds: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        keeper_runtime.wait_for_keeper_ready(context, timeout_s=0.2)


def test_wait_for_keeper_exit_named_pipe_ignores_keyboard_interrupt_during_deadline_checks(monkeypatch) -> None:
    context = SimpleNamespace(paths=SimpleNamespace(ccbd_ipc_kind='named_pipe'))
    states = iter((SimpleNamespace(keeper_pid=123), SimpleNamespace(keeper_pid=0)))
    original_monotonic = time.monotonic
    monotonic_calls = {'count': 0}

    monkeypatch.setattr(
        keeper_runtime,
        'KeeperStateStore',
        lambda paths: SimpleNamespace(load=lambda: next(states)),
    )
    monkeypatch.setattr(
        keeper_runtime,
        'keeper_state_is_running',
        lambda state, process_exists_fn=None: bool(getattr(state, 'keeper_pid', 0)),
    )
    monkeypatch.setattr(keeper_runtime.time, 'sleep', lambda seconds: None)

    def _monotonic() -> float:
        monotonic_calls['count'] += 1
        if monotonic_calls['count'] == 1:
            raise KeyboardInterrupt
        return original_monotonic()

    monkeypatch.setattr(keeper_runtime.time, 'monotonic', _monotonic)

    assert keeper_runtime.wait_for_keeper_exit(context, timeout_s=0.2) is True
    assert monotonic_calls['count'] >= 2

