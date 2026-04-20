from __future__ import annotations

import json
from pathlib import Path

import pytest

from provider_backends.codex.comm_runtime.binding_update_runtime.project_binding import update_project_session_binding


def test_update_project_session_binding_records_old_binding_and_resumes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session_file = tmp_path / ".ccb" / ".codex-agent1-session"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(
        json.dumps(
            {
                "active": False,
                "work_dir": str(tmp_path),
                "codex_session_path": str(tmp_path / "old.jsonl"),
                "codex_session_id": "old-session-id",
                "start_cmd": "export CODEX_RUNTIME_DIR=/tmp/demo; codex -c disable_paste_burst=true",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    log_path = tmp_path / "123e4567-e89b-12d3-a456-426614174000.jsonl"
    log_path.write_text("", encoding="utf-8")

    transfers: list[dict[str, object]] = []
    monkeypatch.setattr(
        "provider_backends.codex.comm_runtime.binding_update_runtime.project_binding_service.compute_ccb_project_id",
        lambda path: f"proj:{Path(path).name}",
    )
    monkeypatch.setattr(
        "provider_backends.codex.comm_runtime.binding_update_runtime.history_transfer_service.maybe_transfer_old_binding",
        lambda **kwargs: transfers.append(kwargs),
    )

    state = update_project_session_binding(
        project_file=session_file,
        log_path=log_path,
        session_info={"work_dir": str(tmp_path)},
    )

    assert state is not None
    assert state.session_id == "123e4567-e89b-12d3-a456-426614174000"
    assert state.resume_cmd is not None
    assert state.resume_cmd.endswith("resume 123e4567-e89b-12d3-a456-426614174000")

    data = json.loads(session_file.read_text(encoding="utf-8"))
    assert data["active"] is True
    assert data["old_codex_session_id"] == "old-session-id"
    assert data["old_codex_session_path"] == str(tmp_path / "old.jsonl")
    assert data["ccb_project_id"] == f"proj:{tmp_path.name}"
    assert transfers == [
        {
            "old_path": str(tmp_path / "old.jsonl"),
            "old_id": "old-session-id",
            "work_dir_hint": str(tmp_path),
        }
    ]
