from __future__ import annotations

import json
from pathlib import Path

from project.identity import compute_ccb_project_id
from provider_backends.gemini.comm_runtime.binding_update_runtime.project_binding import update_project_session_binding
from provider_backends.gemini.comm_runtime.binding_update_runtime.history_transfer import apply_old_binding_metadata


def test_apply_old_binding_metadata_records_old_session_and_path() -> None:
    data = {"work_dir": "/tmp/demo"}

    apply_old_binding_metadata(
        data,
        old_path="/tmp/old/session.json",
        old_id="old-id",
        new_path="/tmp/new/session.json",
        new_id="new-id",
        binding_changed=False,
    )

    assert data["old_gemini_session_id"] == "old-id"
    assert data["old_gemini_session_path"] == "/tmp/old/session.json"
    assert "old_updated_at" not in data


def test_update_project_session_binding_persists_binding_fields(tmp_path: Path) -> None:
    project_file = tmp_path / ".ccb" / ".gemini-session"
    project_file.parent.mkdir(parents=True, exist_ok=True)
    project_file.write_text(json.dumps({"work_dir": str(tmp_path)}), encoding="utf-8")

    session_path = tmp_path / "demo-project" / "chats" / "session-1.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(json.dumps({"sessionId": "gemini-session-id", "messages": []}), encoding="utf-8")

    state = update_project_session_binding(project_file=project_file, session_path=session_path)

    assert state is not None
    assert state.session_path == str(session_path)
    assert state.session_id == "gemini-session-id"
    assert state.ccb_project_id == compute_ccb_project_id(tmp_path)

    data = json.loads(project_file.read_text(encoding="utf-8"))
    assert data["gemini_session_path"] == str(session_path)
    assert data["gemini_session_id"] == "gemini-session-id"
    assert data["gemini_project_hash"] == "demo-project"
    assert data["ccb_project_id"] == compute_ccb_project_id(tmp_path)
