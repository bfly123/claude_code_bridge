from __future__ import annotations

import json
from pathlib import Path

import pytest

from provider_backends.gemini.comm import GeminiCommunicator
from provider_backends.gemini.session import GeminiProjectSession


def test_gemini_session_update_binding_persists_session_fields(tmp_path: Path) -> None:
    cfg = tmp_path / ".ccb"
    cfg.mkdir(parents=True, exist_ok=True)
    session_file = cfg / ".gemini-session"
    session_file.write_text("{}", encoding="utf-8")

    session = GeminiProjectSession(session_file=session_file, data={})
    project_dir = tmp_path / "demo-project"
    session_path = project_dir / "chats" / "session-1.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(json.dumps({"sessionId": "gemini-session-id", "messages": []}), encoding="utf-8")

    session.update_gemini_binding(session_path=session_path, session_id="gemini-session-id")

    data = json.loads(session_file.read_text(encoding="utf-8"))
    assert data["gemini_session_path"] == str(session_path)
    assert data["gemini_session_id"] == "gemini-session-id"
    assert data["gemini_project_hash"] == "demo-project"


def test_gemini_comm_remember_updates_session_file_and_runtime_info(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / ".ccb"
    cfg.mkdir(parents=True, exist_ok=True)
    session_file = cfg / ".gemini-session"
    session_file.write_text(json.dumps({"active": True, "work_dir": str(tmp_path)}), encoding="utf-8")

    project_dir = tmp_path / "demo-project"
    session_path = project_dir / "chats" / "session-1.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(json.dumps({"sessionId": "gemini-session-id", "messages": []}), encoding="utf-8")

    comm = GeminiCommunicator.__new__(GeminiCommunicator)
    comm.project_session_file = str(session_file)
    comm.session_info = {"work_dir": str(tmp_path), "pane_title_marker": "CCB-gemini-demo"}
    comm.ccb_session_id = "ccb-session-id"
    comm.terminal = "tmux"
    comm.pane_id = "%1"

    monkeypatch.setattr("provider_backends.gemini.comm.publish_registry_binding", lambda **kwargs: None)

    comm._remember_gemini_session(session_path)

    data = json.loads(session_file.read_text(encoding="utf-8"))
    assert data["gemini_session_path"] == str(session_path)
    assert data["gemini_session_id"] == "gemini-session-id"
    assert data["gemini_project_hash"] == "demo-project"
    assert comm.session_info["gemini_session_path"] == str(session_path)
    assert comm.session_info["gemini_session_id"] == "gemini-session-id"
