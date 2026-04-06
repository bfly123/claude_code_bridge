from __future__ import annotations

import json
from pathlib import Path

from provider_backends.opencode.runtime.session_runtime import load_opencode_session_info


def test_load_opencode_session_info_merges_env_and_session_file(monkeypatch, tmp_path: Path) -> None:
    session_file = tmp_path / ".opencode-session"
    session_file.write_text(
        json.dumps(
            {
                "opencode_session_path": str(tmp_path / "storage" / "conversation.json"),
                "opencode_session_id": "open-session",
                "opencode_project_id": "open-project",
                "pane_title_marker": "agent1",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("CCB_SESSION_ID", "ccb-1")
    monkeypatch.setenv("OPENCODE_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("OPENCODE_TMUX_SESSION", "%3")
    monkeypatch.delenv("OPENCODE_TERMINAL", raising=False)

    info = load_opencode_session_info(session_finder=lambda: session_file)

    assert info is not None
    assert info["ccb_session_id"] == "ccb-1"
    assert info["runtime_dir"] == str(tmp_path / "runtime")
    assert info["pane_id"] == "%3"
    assert info["opencode_session_path"] == str(tmp_path / "storage" / "conversation.json")
    assert info["opencode_session_id"] == "open-session"
    assert info["opencode_project_id"] == "open-project"
    assert info["pane_title_marker"] == "agent1"
    assert info["_session_file"] == str(session_file)
