from __future__ import annotations

import json
from pathlib import Path

from provider_backends.opencode.comm import OpenCodeCommunicator


def test_opencode_comm_load_session_info_backfills_project_fields(tmp_path: Path, monkeypatch) -> None:
    session_file = tmp_path / ".opencode-session"
    runtime_dir = tmp_path / "run"
    runtime_dir.mkdir()
    session_file.write_text(
        json.dumps(
            {
                "active": True,
                "runtime_dir": str(runtime_dir),
                "terminal": "tmux",
                "pane_id": "%1",
                "work_dir": str(tmp_path),
                "ccb_session_id": "ccb-opencode-test",
                "opencode_session_id": "ses_123",
                "opencode_project_id": "proj_123",
            }
        ),
        encoding="utf-8",
    )

    comm = OpenCodeCommunicator.__new__(OpenCodeCommunicator)
    monkeypatch.setattr(OpenCodeCommunicator, "_find_session_file", lambda self: session_file)

    data = comm._load_session_info()

    assert data is not None
    assert data["_session_file"] == str(session_file)
    assert data["opencode_session_id"] == "ses_123"
    assert data["opencode_project_id"] == "proj_123"


def test_opencode_comm_find_session_file_prefers_ccb_session_file(tmp_path: Path, monkeypatch) -> None:
    session = tmp_path / "proj" / ".ccb" / ".opencode-session"
    session.parent.mkdir(parents=True)
    session.write_text("{}", encoding="utf-8")
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.setenv("CCB_SESSION_FILE", str(session))

    comm = OpenCodeCommunicator.__new__(OpenCodeCommunicator)
    assert comm._find_session_file() == session
