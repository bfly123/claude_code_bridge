from __future__ import annotations

import json
from pathlib import Path

from provider_backends.claude.comm_runtime.binding_runtime.session import (
    remember_claude_session_binding,
)


def test_binding_runtime_session_infers_work_dir_and_records_history(tmp_path: Path) -> None:
    project_session_file = tmp_path / ".claude-session"
    project_session_file.write_text(
        json.dumps(
            {
                "claude_session_id": "old-id",
                "claude_session_path": str(tmp_path / "old-id.jsonl"),
            }
        ),
        encoding="utf-8",
    )
    written: list[dict] = []

    data = remember_claude_session_binding(
        project_session_file=project_session_file,
        session_path=tmp_path / "new-id.jsonl",
        session_info={},
        infer_work_dir_from_session_file_fn=lambda path: tmp_path / "repo",
        ensure_claude_session_work_dir_fields_fn=lambda data, path: None,
        safe_write_session_fn=lambda path, payload: written.append(json.loads(payload)) or (True, None),
        now_str_fn=lambda: "2026-04-06 12:00:00",
    )

    assert data is not None
    assert data["work_dir"] == str(tmp_path / "repo")
    assert data["old_claude_session_id"] == "old-id"
    assert data["old_updated_at"] == "2026-04-06 12:00:00"
    assert data["updated_at"] == "2026-04-06 12:00:00"
    assert written[0]["claude_session_id"] == "new-id"


def test_binding_runtime_session_returns_none_when_write_fails(tmp_path: Path) -> None:
    project_session_file = tmp_path / ".claude-session"
    project_session_file.write_text("{}", encoding="utf-8")

    data = remember_claude_session_binding(
        project_session_file=project_session_file,
        session_path=tmp_path / "new-id.jsonl",
        session_info={"work_dir": str(tmp_path / "repo")},
        infer_work_dir_from_session_file_fn=lambda path: tmp_path / "fallback",
        ensure_claude_session_work_dir_fields_fn=lambda data, path: None,
        safe_write_session_fn=lambda path, payload: (False, "write_failed"),
        now_str_fn=lambda: "2026-04-06 12:00:00",
    )

    assert data is None
