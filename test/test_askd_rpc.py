from __future__ import annotations

import json
import socket
from pathlib import Path

import askd_rpc


class _NoReplySocket:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def settimeout(self, _timeout):
        return None

    def sendall(self, _data):
        return None

    def recv(self, _n):
        raise socket.timeout()


class _ShutdownTimeoutSocket(_NoReplySocket):
    pass


def _write_state(path: Path) -> None:
    path.write_text(
        json.dumps({"host": "127.0.0.1", "port": 12345, "token": "tkn"}, ensure_ascii=True),
        encoding="utf-8",
    )


def test_ping_daemon_times_out_without_hanging(tmp_path: Path, monkeypatch) -> None:
    state_file = tmp_path / "askd.json"
    _write_state(state_file)
    monkeypatch.setattr(askd_rpc.socket, "create_connection", lambda *_args, **_kwargs: _NoReplySocket())

    ok = askd_rpc.ping_daemon("ask", timeout_s=0.01, state_file=state_file)
    assert ok is False


def test_shutdown_daemon_tolerates_read_timeout(tmp_path: Path, monkeypatch) -> None:
    state_file = tmp_path / "askd.json"
    _write_state(state_file)
    monkeypatch.setattr(askd_rpc.socket, "create_connection", lambda *_args, **_kwargs: _ShutdownTimeoutSocket())

    ok = askd_rpc.shutdown_daemon("ask", timeout_s=0.01, state_file=state_file)
    assert ok is True
