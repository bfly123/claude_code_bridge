from __future__ import annotations

from types import SimpleNamespace

import pytest

import ccbd.daemon_process as daemon_process
from ccbd.socket_client import CcbdClientError


def test_ready_probe_timeout_uses_named_pipe_value() -> None:
    assert daemon_process._ready_probe_timeout_s('named_pipe') == 1.0
    assert daemon_process._ready_probe_timeout_s('unix_socket') == 0.2


def test_wait_for_ccbd_ready_uses_named_pipe_probe_timeout(monkeypatch) -> None:
    seen: list[tuple[float | None, str | None, str]] = []

    class FakeClient:
        def __init__(self, socket_path, *, timeout_s=None, ipc_kind=None) -> None:
            del socket_path
            seen.append((timeout_s, ipc_kind, 'init'))

        def ping(self, target: str) -> dict:
            seen.append((None, None, target))
            return {'mount_state': 'mounted'}

    process = SimpleNamespace(poll=lambda: None, returncode=None)
    monkeypatch.setattr(daemon_process, 'CcbdClient', FakeClient)

    daemon_process._wait_for_ccbd_ready(
        process=process,
        socket_path=r'\\.\pipe\ccb-test',
        ipc_kind='named_pipe',
        timeout_s=1.0,
    )

    assert seen == [(1.0, 'named_pipe', 'init'), (None, None, 'ccbd')]


def test_wait_for_ccbd_ready_raises_exit_error_after_final_probe(monkeypatch) -> None:
    seen: list[float | None] = []

    class FakeClient:
        def __init__(self, socket_path, *, timeout_s=None, ipc_kind=None) -> None:
            del socket_path, ipc_kind
            seen.append(timeout_s)

        def ping(self, target: str) -> dict:
            del target
            raise CcbdClientError('not ready')

    process = SimpleNamespace(poll=lambda: 0, returncode=7)
    monkeypatch.setattr(daemon_process, 'CcbdClient', FakeClient)

    with pytest.raises(daemon_process.CcbdProcessError, match='code 7'):
        daemon_process._wait_for_ccbd_ready(
            process=process,
            socket_path=r'\\.\pipe\ccb-test',
            ipc_kind='named_pipe',
            timeout_s=1.0,
        )

    assert seen == [1.0, 1.0]
