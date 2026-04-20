from __future__ import annotations

import json
from pathlib import Path

from provider_backends.claude.comm_runtime.conversations import latest_conversations, latest_message


def _write_session(path: Path, entries: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for entry in entries:
        if isinstance(entry, str):
            lines.append(entry)
        else:
            lines.append(json.dumps(entry, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_latest_message_returns_last_assistant_message(monkeypatch, tmp_path: Path) -> None:
    session = tmp_path / "session.jsonl"
    _write_session(
        session,
        [
            "",
            "{invalid json",
            {
                "type": "user",
                "content": [{"type": "text", "text": "hello"}],
            },
            {
                "type": "event_msg",
                "payload": {"type": "assistant_message", "role": "assistant", "text": "first"},
            },
            {
                "type": "event_msg",
                "payload": {"type": "assistant_message", "role": "assistant", "text": "second"},
            },
        ],
    )
    monkeypatch.setattr(
        "provider_backends.claude.comm_runtime.conversations.latest_session",
        lambda reader: session,
    )

    assert latest_message(object()) == "second"


def test_latest_conversations_pairs_user_and_assistant_messages(monkeypatch, tmp_path: Path) -> None:
    session = tmp_path / "session.jsonl"
    _write_session(
        session,
        [
            {
                "type": "user",
                "content": [{"type": "text", "text": "u1"}],
            },
            {
                "type": "event_msg",
                "payload": {"type": "assistant_message", "role": "assistant", "text": "a1"},
            },
            {
                "type": "user",
                "content": [{"type": "text", "text": "u2"}],
            },
            {
                "type": "event_msg",
                "payload": {"type": "assistant_message", "role": "assistant", "text": "a2"},
            },
            {
                "type": "event_msg",
                "payload": {"type": "assistant_message", "role": "assistant", "text": "a3"},
            },
        ],
    )
    monkeypatch.setattr(
        "provider_backends.claude.comm_runtime.conversations.latest_session",
        lambda reader: session,
    )

    assert latest_conversations(object(), 2) == [("u2", "a2"), ("", "a3")]
