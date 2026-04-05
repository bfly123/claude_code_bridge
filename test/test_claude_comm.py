from __future__ import annotations

import json
import os
from pathlib import Path

from provider_backends.claude.comm import ClaudeLogReader
from provider_backends.claude.session import load_project_session


def _project_key(path: Path) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in str(path))


def _write_session(path: Path, text: str = "hello") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"'
        + text
        + '"}]}}\n',
        encoding="utf-8",
    )


def test_set_preferred_session_rejects_foreign_project_session(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "claude-root"
    work_dir = tmp_path / "project-a"
    other_dir = tmp_path / "project-b"
    work_dir.mkdir()
    other_dir.mkdir()
    monkeypatch.setenv("PWD", str(work_dir))

    own_session = root / _project_key(work_dir) / "own.jsonl"
    foreign_session = root / _project_key(other_dir) / "foreign.jsonl"
    _write_session(own_session, text="own")
    _write_session(foreign_session, text="foreign")
    os.utime(foreign_session, (foreign_session.stat().st_atime + 10, foreign_session.stat().st_mtime + 10))

    reader = ClaudeLogReader(root=root, work_dir=work_dir, use_sessions_index=False)
    reader.set_preferred_session(foreign_session)

    assert reader._preferred_session is None
    assert reader.current_session_path() == own_session


def test_set_preferred_session_accepts_current_project_session(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "claude-root"
    work_dir = tmp_path / "project-a"
    work_dir.mkdir()
    monkeypatch.setenv("PWD", str(work_dir))

    own_session = root / _project_key(work_dir) / "own.jsonl"
    _write_session(own_session, text="own")

    reader = ClaudeLogReader(root=root, work_dir=work_dir, use_sessions_index=False)
    reader.set_preferred_session(own_session)

    assert reader._preferred_session == own_session
    assert reader.current_session_path() == own_session


def test_load_project_session_prefers_project_anchor_session_file(tmp_path: Path) -> None:
    project_root = tmp_path / "repo"
    workspace = project_root / ".ccb" / "workspaces" / "claude"
    session_file = project_root / ".ccb" / ".claude-session"
    workspace.mkdir(parents=True)
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(
        json.dumps(
            {
                "terminal": "tmux",
                "pane_id": "%2",
                "work_dir": str(workspace),
                "ccb_session_id": "ccb-claude-test",
            }
        ),
        encoding="utf-8",
    )

    session = load_project_session(workspace)

    assert session is not None
    assert session.session_file == session_file
    assert session.pane_id == "%2"
