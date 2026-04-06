from __future__ import annotations

import json
from pathlib import Path

from opencode_runtime.watch import handle_opencode_session_event


def test_handle_opencode_session_event_updates_bound_session(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir()
    work_dir = tmp_path / "workspace-agent2"
    work_dir.mkdir()
    (work_dir / ".ccb-workspace.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "record_type": "workspace_binding",
                "target_project": str(project_root),
                "project_id": "demo-project",
                "agent_name": "agent2",
                "workspace_mode": "linked",
                "workspace_path": str(work_dir),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    session_file = project_root / ".ccb" / ".opencode-agent2-session"
    session_file.parent.mkdir(parents=True)
    session_file.write_text("{}", encoding="utf-8")

    session_path = tmp_path / "proj-1" / "ses_1.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        json.dumps({"directory": str(work_dir), "id": "ses-1"}),
        encoding="utf-8",
    )

    calls: list[tuple[str | None, str | None]] = []

    class _Session:
        def update_opencode_binding(self, *, session_id: str | None, project_id: str | None) -> None:
            calls.append((session_id, project_id))

    monkeypatch.setattr(
        "provider_backends.opencode.session.load_project_session",
        lambda work_dir, instance=None: _Session() if instance == "agent2" else None,
    )
    monkeypatch.setattr(
        "provider_backends.opencode.session.find_project_session_file",
        lambda work_dir, instance=None: session_file if instance == "agent2" else None,
    )

    handle_opencode_session_event(session_path)

    assert calls == [("ses-1", "proj-1")]
