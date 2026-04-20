from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from provider_backends.droid.comm_runtime.polling_runtime.loop import read_since, read_since_events


def test_droid_read_since_resets_state_when_session_rotates(tmp_path: Path, monkeypatch) -> None:
    session = tmp_path / "session.jsonl"
    session.write_bytes(b'{"type":"assistant","content":[{"type":"text","text":"hello"}]}\n')
    reader = SimpleNamespace(_poll_interval=0.0)

    monkeypatch.setattr(
        "provider_backends.droid.comm_runtime.polling_runtime.loop.latest_session",
        lambda reader_obj: session,
    )

    message, state = read_since(
        reader,
        {"session_path": tmp_path / "old.jsonl", "offset": 999, "carry": b"stale"},
        timeout=0.0,
        block=False,
    )

    assert message == "hello"
    assert state["session_path"] == session
    assert state["carry"] == b""
    assert int(state["offset"]) == int(session.stat().st_size)


def test_droid_read_since_events_returns_empty_when_session_missing_non_blocking(monkeypatch) -> None:
    reader = SimpleNamespace(_poll_interval=0.0)
    monkeypatch.setattr(
        "provider_backends.droid.comm_runtime.polling_runtime.loop.latest_session",
        lambda reader_obj: None,
    )

    events, state = read_since_events(reader, {"offset": 5}, timeout=0.0, block=False)

    assert events == []
    assert state == {"offset": 5}
