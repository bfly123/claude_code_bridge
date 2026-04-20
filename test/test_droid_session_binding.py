from __future__ import annotations

import json
from pathlib import Path

import pytest

from project.identity import compute_ccb_project_id
from provider_backends.droid.session import DroidProjectSession


def test_droid_session_update_binding_persists_binding_and_old_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / ".ccb"
    cfg.mkdir(parents=True, exist_ok=True)
    session_file = cfg / ".droid-session"
    session_file.write_text(
        json.dumps(
            {
                "active": False,
                "work_dir": str(tmp_path),
                "droid_session_path": "/tmp/old/session.log",
                "droid_session_id": "old-session",
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

    session = DroidProjectSession(
        session_file=session_file,
        data=json.loads(session_file.read_text(encoding="utf-8")),
    )
    new_path = tmp_path / "logs" / "new-session.log"
    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.write_text("", encoding="utf-8")

    session.update_droid_binding(session_path=new_path, session_id=None)

    data = json.loads(session_file.read_text(encoding="utf-8"))
    assert data["droid_session_path"] == str(new_path)
    assert data["droid_session_id"] == "new-session"
    assert data["ccb_project_id"] == compute_ccb_project_id(tmp_path)
    assert data["old_droid_session_path"] == "/tmp/old/session.log"
    assert data["old_droid_session_id"] == "old-session"
    assert "old_updated_at" in data
    assert data["updated_at"]
    assert data["active"] is True
    assert transfer_calls == [("/tmp/old/session.log", "old-session")]
