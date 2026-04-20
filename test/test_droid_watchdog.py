from __future__ import annotations

import json
from pathlib import Path

from provider_backends.droid.comm_runtime.watchdog import handle_droid_session_event


def test_handle_droid_session_event_updates_named_agent_session(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    work_dir = tmp_path / "workspace-agent4"
    work_dir.mkdir()
    (work_dir / ".ccb-workspace.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "record_type": "workspace_binding",
                "target_project": str(project_root),
                "project_id": "demo-project",
                "agent_name": "agent4",
                "workspace_mode": "linked",
                "workspace_path": str(work_dir),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    session_file = project_root / ".ccb" / ".droid-agent4-session"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text("{}", encoding="utf-8")

    event_path = tmp_path / "logs" / "session.jsonl"
    event_path.parent.mkdir(parents=True, exist_ok=True)
    event_path.write_text('{"type":"session_start","cwd":"ignored","id":"ignored"}\n', encoding="utf-8")

    calls: list[tuple[Path, str | None]] = []

    class _Session:
        def update_droid_binding(self, *, session_path: Path, session_id: str | None) -> None:
            calls.append((session_path, session_id))

    monkeypatch.setattr(
        "provider_backends.droid.comm_runtime.watchdog.read_droid_session_start",
        lambda path: (str(work_dir), "sid-42"),
    )

    handle_droid_session_event(
        event_path,
        find_project_session_file_fn=lambda cwd, instance=None: session_file if instance == "agent4" else None,
        load_project_session_fn=lambda cwd, instance=None: _Session() if instance == "agent4" else None,
    )

    assert calls == [(event_path, "sid-42")]
