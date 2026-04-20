from __future__ import annotations

import json
from pathlib import Path

from provider_backends.codex.comm_runtime.session_runtime_runtime.discovery import find_codex_session_file


def test_find_codex_session_file_uses_workspace_binding_named_agent(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    workspace = tmp_path / "workspace-agent2"
    workspace.mkdir()
    (workspace / ".ccb-workspace.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "record_type": "workspace_binding",
                "target_project": str(project_root),
                "project_id": "demo-project",
                "agent_name": "agent2",
                "workspace_mode": "linked",
                "workspace_path": str(workspace),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    session_file = project_root / ".ccb" / ".codex-agent2-session"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text("{}", encoding="utf-8")

    assert find_codex_session_file(cwd=workspace) == session_file
