from __future__ import annotations

import json
from pathlib import Path

from provider_backends.droid.comm_runtime.session_content import capture_state, latest_conversations, latest_message


def _write_session(path: Path, entries: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for entry in entries:
        if isinstance(entry, str):
            lines.append(entry)
        else:
            lines.append(json.dumps(entry, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_droid_capture_state_uses_latest_session_size(monkeypatch, tmp_path: Path) -> None:
    session = tmp_path / "session.jsonl"
    _write_session(session, [{"type": "assistant", "content": [{"type": "text", "text": "hello"}]}])
    monkeypatch.setattr(
        "provider_backends.droid.comm_runtime.session_content.latest_session",
        lambda reader: session,
    )

    state = capture_state(object())

    assert state["session_path"] == session
    assert state["offset"] == session.stat().st_size
    assert state["carry"] == b""


def test_droid_latest_message_returns_last_assistant_message(monkeypatch, tmp_path: Path) -> None:
    session = tmp_path / "session.jsonl"
    _write_session(
        session,
        [
            "",
            "{bad json",
            {"type": "user", "content": [{"type": "text", "text": "q1"}]},
            {"type": "assistant", "content": [{"type": "text", "text": "a1"}]},
            {"type": "assistant", "content": [{"type": "text", "text": "a2"}]},
        ],
    )
    monkeypatch.setattr(
        "provider_backends.droid.comm_runtime.session_content.latest_session",
        lambda reader: session,
    )

    assert latest_message(object()) == "a2"


def test_droid_latest_conversations_pairs_user_and_assistant_messages(monkeypatch, tmp_path: Path) -> None:
    session = tmp_path / "session.jsonl"
    _write_session(
        session,
        [
            {"type": "user", "content": [{"type": "text", "text": "q1"}]},
            {"type": "assistant", "content": [{"type": "text", "text": "a1"}]},
            {"type": "user", "content": [{"type": "text", "text": "q2"}]},
            {"type": "assistant", "content": [{"type": "text", "text": "a2"}]},
        ],
    )
    monkeypatch.setattr(
        "provider_backends.droid.comm_runtime.session_content.latest_session",
        lambda reader: session,
    )

    assert latest_conversations(object(), n=1) == [("q2", "a2")]
    assert latest_conversations(object(), n=2) == [("q1", "a1"), ("q2", "a2")]


def test_droid_latest_conversations_returns_empty_for_non_positive_n(monkeypatch, tmp_path: Path) -> None:
    session = tmp_path / "session.jsonl"
    _write_session(session, [])
    monkeypatch.setattr(
        "provider_backends.droid.comm_runtime.session_content.latest_session",
        lambda reader: session,
    )

    assert latest_conversations(object(), n=0) == []
