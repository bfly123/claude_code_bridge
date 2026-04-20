from __future__ import annotations

import json
from pathlib import Path

from provider_backends.gemini.comm_runtime.session_runtime import load_gemini_session_info


def test_load_gemini_session_info_merges_env_and_session_file(monkeypatch, tmp_path: Path) -> None:
    session_file = tmp_path / ".gemini-session"
    session_file.write_text(
        json.dumps(
            {
                "gemini_session_path": str(tmp_path / "session.json"),
                "pane_id": "%3",
                "tmux_session": "%3",
                "pane_title_marker": "agent1",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CCB_SESSION_ID", "ccb-1")
    monkeypatch.setenv("GEMINI_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("GEMINI_TMUX_SESSION", "")
    monkeypatch.setattr(
        "provider_backends.gemini.comm_runtime.session_runtime.read_gemini_session_id",
        lambda path: "gemini-sid" if path == Path(str(tmp_path / "session.json")) else None,
    )

    info = load_gemini_session_info(session_finder=lambda: session_file)

    assert info is not None
    assert info["ccb_session_id"] == "ccb-1"
    assert info["gemini_session_path"] == str(tmp_path / "session.json")
    assert info["gemini_session_id"] == "gemini-sid"
    assert info["pane_id"] == "%3"
    assert info["pane_title_marker"] == "agent1"


def test_load_gemini_session_info_returns_none_for_inactive_project_session(
    tmp_path: Path,
) -> None:
    session_file = tmp_path / ".gemini-session"
    session_file.write_text(json.dumps({"active": False}), encoding="utf-8")

    info = load_gemini_session_info(session_finder=lambda: session_file)

    assert info is None
