from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from provider_backends.gemini.comm_runtime.session_content import (
    capture_state,
    latest_conversations,
    latest_message,
)


def _write_session(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
        return
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _reader() -> SimpleNamespace:
    return SimpleNamespace(_poll_interval=0.0)


def test_gemini_capture_state_reports_last_gemini_metadata(monkeypatch, tmp_path: Path) -> None:
    session = tmp_path / "session.json"
    _write_session(
        session,
        {
            "messages": [
                {"type": "user", "content": "q1"},
                {"type": "gemini", "id": "g1", "content": "a1"},
                {"type": "gemini", "id": "g2", "content": "a2"},
            ]
        },
    )
    monkeypatch.setattr(
        "provider_backends.gemini.comm_runtime.session_content.latest_session",
        lambda reader: session,
    )

    state = capture_state(_reader())

    assert state["session_path"] == session
    assert state["msg_count"] == 3
    assert state["last_gemini_id"] == "g2"
    assert state["last_gemini_hash"] == hashlib.sha256(b"a2").hexdigest()


def test_gemini_capture_state_marks_invalid_json_as_unknown(monkeypatch, tmp_path: Path) -> None:
    session = tmp_path / "session.json"
    _write_session(session, "{bad json")
    monkeypatch.setattr(
        "provider_backends.gemini.comm_runtime.session_content.latest_session",
        lambda reader: session,
    )

    state = capture_state(_reader())

    assert state["session_path"] == session
    assert state["msg_count"] == -1
    assert state["last_gemini_id"] is None
    assert state["last_gemini_hash"] is None


def test_gemini_latest_message_returns_last_gemini_content(monkeypatch, tmp_path: Path) -> None:
    session = tmp_path / "session.json"
    _write_session(
        session,
        {
            "messages": [
                {"type": "user", "content": "q1"},
                {"type": "gemini", "content": "a1"},
                {"type": "gemini", "content": "a2"},
            ]
        },
    )
    monkeypatch.setattr(
        "provider_backends.gemini.comm_runtime.session_content.latest_session",
        lambda reader: session,
    )

    assert latest_message(_reader()) == "a2"


def test_gemini_latest_conversations_pairs_user_and_gemini_messages(monkeypatch, tmp_path: Path) -> None:
    session = tmp_path / "session.json"
    _write_session(
        session,
        {
            "messages": [
                {"type": "user", "content": "q1"},
                {"type": "gemini", "content": "a1"},
                {"type": "user", "content": "q2"},
                {"type": "gemini", "content": "a2"},
                {"type": "gemini", "content": "a3"},
            ]
        },
    )
    monkeypatch.setattr(
        "provider_backends.gemini.comm_runtime.session_content.latest_session",
        lambda reader: session,
    )

    assert latest_conversations(_reader(), n=2) == [("q2", "a2"), ("", "a3")]


def test_gemini_latest_conversations_returns_empty_for_non_positive_n(
    monkeypatch,
    tmp_path: Path,
) -> None:
    session = tmp_path / "session.json"
    _write_session(session, {"messages": []})
    monkeypatch.setattr(
        "provider_backends.gemini.comm_runtime.session_content.latest_session",
        lambda reader: session,
    )

    assert latest_conversations(_reader(), n=0) == []
