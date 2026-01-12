from __future__ import annotations

import json
from pathlib import Path

from oaskd_session import load_project_session


def _write_session(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_opencode_session_splits_ccb_and_storage_ids(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    session_file = tmp_path / ".opencode-session"
    _write_session(
        session_file,
        {
            "session_id": "ai-123",
            "runtime_dir": str(tmp_path / "run"),
            "terminal": "tmux",
            "pane_id": "%1",
            "pane_title_marker": "CCB-opencode-ai-123",
            "work_dir": str(tmp_path),
            "active": True,
        },
    )

    session = load_project_session(tmp_path)
    assert session is not None
    assert session.session_id == "ai-123"
    assert session.ccb_session_id == "ai-123"
    assert session.opencode_session_id == ""
    assert session.opencode_session_id_filter is None


def test_opencode_session_update_binding_persists_storage_ids(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    session_file = tmp_path / ".opencode-session"
    _write_session(
        session_file,
        {
            "session_id": "ai-123",
            "runtime_dir": str(tmp_path / "run"),
            "terminal": "tmux",
            "pane_id": "%1",
            "work_dir": str(tmp_path),
            "active": True,
        },
    )

    session = load_project_session(tmp_path)
    assert session is not None
    session.update_opencode_binding(session_id="ses_abc", project_id="proj1")

    session2 = load_project_session(tmp_path)
    assert session2 is not None
    assert session2.opencode_session_id == "ses_abc"
    assert session2.opencode_project_id == "proj1"
    assert session2.opencode_session_id_filter == "ses_abc"


def test_opencode_session_legacy_session_id_as_storage_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    session_file = tmp_path / ".opencode-session"
    _write_session(
        session_file,
        {
            "session_id": "ses_legacy",
            "runtime_dir": str(tmp_path / "run"),
            "terminal": "tmux",
            "pane_id": "%1",
            "work_dir": str(tmp_path),
            "active": True,
        },
    )

    session = load_project_session(tmp_path)
    assert session is not None
    assert session.opencode_session_id == "ses_legacy"
    assert session.opencode_session_id_filter == "ses_legacy"

