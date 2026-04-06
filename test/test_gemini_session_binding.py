from __future__ import annotations

import json
from pathlib import Path

import pytest

from project.identity import compute_ccb_project_id
from provider_backends.gemini.session import GeminiProjectSession


def test_gemini_session_update_binding_records_old_metadata_and_project_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / ".ccb"
    cfg.mkdir(parents=True, exist_ok=True)
    session_file = cfg / ".gemini-session"
    session_file.write_text(
        json.dumps(
            {
                "active": False,
                "work_dir": str(tmp_path),
                "gemini_session_path": "/tmp/old/session.json",
                "gemini_session_id": "old-session",
            }
        ),
        encoding="utf-8",
    )

    transfer_calls: list[tuple[str | None, str | None]] = []
    monkeypatch.setattr(
        "memory.transfer_runtime.maybe_auto_transfer",
        lambda **kwargs: transfer_calls.append(
            (
                str(kwargs.get("session_path")) if kwargs.get("session_path") is not None else None,
                kwargs.get("session_id"),
            )
        ),
    )

    session = GeminiProjectSession(
        session_file=session_file,
        data=json.loads(session_file.read_text(encoding="utf-8")),
    )
    new_path = tmp_path / "demo-project" / "chats" / "session-2.json"
    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.write_text("{}", encoding="utf-8")

    session.update_gemini_binding(session_path=new_path, session_id=None)

    data = json.loads(session_file.read_text(encoding="utf-8"))
    assert data["gemini_session_path"] == str(new_path)
    assert data["gemini_session_id"] == "session-2"
    assert data["gemini_project_hash"] == "demo-project"
    assert data["ccb_project_id"] == compute_ccb_project_id(tmp_path)
    assert data["old_gemini_session_path"] == "/tmp/old/session.json"
    assert data["old_gemini_session_id"] == "old-session"
    assert data["active"] is True
    assert transfer_calls == [("/tmp/old/session.json", "old-session")]
