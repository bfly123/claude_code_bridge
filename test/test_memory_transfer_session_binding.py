from __future__ import annotations

import json
import os
from pathlib import Path
import time

from memory.transfer_runtime.conversations import auto_source_candidates, load_session_data


def test_load_session_data_uses_workspace_binding_named_agent(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    workspace = tmp_path / "workspace-agent4"
    workspace.mkdir()
    (workspace / ".ccb-workspace.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "record_type": "workspace_binding",
                "target_project": str(project_root),
                "project_id": "demo-project",
                "agent_name": "agent4",
                "workspace_mode": "linked",
                "workspace_path": str(workspace),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    session_file = project_root / ".ccb" / ".codex-agent4-session"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(json.dumps({"codex_session_id": "sid-1"}), encoding="utf-8")

    resolved, data = load_session_data(workspace, {"codex": ".codex-session"}, "codex")

    assert resolved == session_file
    assert data["codex_session_id"] == "sid-1"


def test_auto_source_candidates_prefers_bound_agent_session(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    workspace = tmp_path / "workspace-agent4"
    workspace.mkdir()
    (workspace / ".ccb-workspace.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "record_type": "workspace_binding",
                "target_project": str(project_root),
                "project_id": "demo-project",
                "agent_name": "agent4",
                "workspace_mode": "linked",
                "workspace_path": str(workspace),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    codex_session = project_root / ".ccb" / ".codex-agent4-session"
    codex_session.parent.mkdir(parents=True, exist_ok=True)
    codex_session.write_text("{}", encoding="utf-8")
    gemini_session = project_root / ".ccb" / ".gemini-agent4-session"
    gemini_session.write_text("{}", encoding="utf-8")
    now = time.time()
    os.utime(codex_session, (now - 10, now - 10))
    os.utime(gemini_session, (now, now))

    ordered = auto_source_candidates(
        workspace,
        ("codex", "gemini"),
        {"codex": ".codex-session", "gemini": ".gemini-session"},
    )

    assert ordered[:2] == ["gemini", "codex"]
