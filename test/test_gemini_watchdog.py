from __future__ import annotations

import json
from pathlib import Path

from provider_backends.gemini.comm_runtime.watchdog import handle_gemini_session_event


def test_handle_gemini_session_event_updates_bound_project_sessions(tmp_path: Path) -> None:
    session_path = tmp_path / "hash1" / "chats" / "session-1.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text("{}", encoding="utf-8")

    project_root = tmp_path / "project"
    project_root.mkdir()
    work_dir = tmp_path / "workspace-agent3"
    work_dir.mkdir()
    (work_dir / ".ccb-workspace.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "record_type": "workspace_binding",
                "target_project": str(project_root),
                "project_id": "demo-project",
                "agent_name": "agent3",
                "workspace_mode": "linked",
                "workspace_path": str(work_dir),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    session_file = project_root / ".ccb" / ".gemini-agent3-session"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text("{}", encoding="utf-8")

    calls: list[tuple[Path, str | None, str | None]] = []

    class _Session:
        def update_gemini_binding(self, *, session_path: Path, session_id: str | None) -> None:
            calls.append((session_path, session_id, "updated"))

    handle_gemini_session_event(
        session_path,
        gemini_root=tmp_path,
        work_dirs_for_hash=lambda project_hash, root: [work_dir] if project_hash == "hash1" else [],
        session_id_reader=lambda path: "session-id",
        session_file_finder=lambda wd, instance: session_file if instance == "agent3" else None,
        session_loader=lambda wd, instance: _Session() if instance == "agent3" else None,
    )

    assert calls == [(session_path, "session-id", "updated")]
