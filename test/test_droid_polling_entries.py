from __future__ import annotations

from pathlib import Path

from provider_backends.droid.comm_runtime.polling_runtime.entries import (
    read_new_entries,
    read_new_events,
    read_new_messages,
)


def test_droid_polling_entries_track_carry_and_events(tmp_path: Path) -> None:
    session = tmp_path / "session.jsonl"
    session.write_bytes(b'{"type":"assistant","content":[{"type":"text","text":"a1"}]}\n{"type":"user"')

    entries, state = read_new_entries(session, {})

    assert entries == [{"type": "assistant", "content": [{"type": "text", "text": "a1"}]}]
    assert state["carry"] == b'{"type":"user"'

    with session.open("ab") as handle:
        handle.write(b',"content":[{"type":"text","text":"q1"}]}\n')

    events, state = read_new_events(session, state)

    assert events == [("user", "q1")]
    assert state["carry"] == b""


def test_droid_polling_entries_reset_offset_after_rotation(tmp_path: Path) -> None:
    session = tmp_path / "session.jsonl"
    session.write_bytes(b'{"type":"assistant","content":[{"type":"text","text":"latest"}]}\n')

    latest, state = read_new_messages(session, {"offset": 999, "carry": b"stale"})

    assert latest == "latest"
    assert state["offset"] == session.stat().st_size
    assert state["carry"] == b""
