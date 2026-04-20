from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from provider_backends.gemini.comm_runtime.polling_loop_runtime.service import read_since


def _reader() -> SimpleNamespace:
    return SimpleNamespace(_poll_interval=0.0, _force_read_interval=0.0)


def test_read_since_returns_missing_session_state_when_not_blocking(monkeypatch) -> None:
    monkeypatch.setattr(
        "provider_backends.gemini.comm_runtime.polling_loop_runtime.service_runtime.refresh_latest_session",
        lambda reader, cursor: None,
    )
    monkeypatch.setattr(
        "provider_backends.gemini.comm_runtime.polling_loop_runtime.service_runtime.latest_session",
        lambda reader: None,
    )

    reply, state = read_since(_reader(), {}, timeout=0.1, block=False)

    assert reply is None
    assert state["session_path"] is None
    assert state["msg_count"] == 0


def test_read_since_returns_reply_for_unknown_baseline(monkeypatch, tmp_path: Path) -> None:
    session = tmp_path / "session-1.json"
    session.write_text(
        json.dumps({"messages": [{"type": "gemini", "id": "g1", "content": "hello from gemini"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "provider_backends.gemini.comm_runtime.polling_loop_runtime.service_runtime.refresh_latest_session",
        lambda reader, cursor: None,
    )
    monkeypatch.setattr(
        "provider_backends.gemini.comm_runtime.polling_loop_runtime.service_runtime.latest_session",
        lambda reader: session,
    )

    reply, state = read_since(
        _reader(),
        {"msg_count": -1, "mtime": 0.0, "mtime_ns": 0, "size": 0},
        timeout=0.1,
        block=False,
    )

    assert reply == "hello from gemini"
    assert state["session_path"] == session
    assert state["msg_count"] == 1
    assert state["last_gemini_id"] == "g1"


def test_read_since_returns_changed_last_reply_without_message_growth(monkeypatch, tmp_path: Path) -> None:
    session = tmp_path / "session-2.json"
    session.write_text(
        json.dumps({"messages": [{"type": "gemini", "id": "g1", "content": "updated reply"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "provider_backends.gemini.comm_runtime.polling_loop_runtime.service_runtime.refresh_latest_session",
        lambda reader, cursor: None,
    )
    monkeypatch.setattr(
        "provider_backends.gemini.comm_runtime.polling_loop_runtime.service_runtime.latest_session",
        lambda reader: session,
    )

    reply, state = read_since(
        _reader(),
        {
            "msg_count": 1,
            "mtime": 0.0,
            "mtime_ns": 0,
            "size": 0,
            "last_gemini_id": "g1",
            "last_gemini_hash": "stale-hash",
        },
        timeout=0.1,
        block=False,
    )

    assert reply == "updated reply"
    assert state["session_path"] == session
    assert state["msg_count"] == 1
    assert state["last_gemini_id"] == "g1"
    assert state["last_gemini_hash"] != "stale-hash"
