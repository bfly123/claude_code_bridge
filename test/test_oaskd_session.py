from __future__ import annotations

import json
from pathlib import Path

import oaskd_session
from oaskd_session import load_project_session


def _write_session(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_opencode_session_splits_ccb_and_storage_ids(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    session_file = tmp_path / ".opencode-session"
    _write_session(
        session_file,
        {
            "session_id": "ai-123",
            "runtime_dir": str(tmp_path / "run"),
            "terminal": "tmux",
            "pane_id": "%1",
            "pane_title_marker": "CCB-opencode-ai-123",
            "work_dir": str(tmp_path),
            "active": True,
        },
    )

    session = load_project_session(tmp_path)
    assert session is not None
    assert session.session_id == "ai-123"
    assert session.ccb_session_id == "ai-123"
    assert session.opencode_session_id == ""
    assert session.opencode_session_id_filter is None


def test_opencode_session_update_binding_persists_storage_ids(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    session_file = tmp_path / ".opencode-session"
    _write_session(
        session_file,
        {
            "session_id": "ai-123",
            "runtime_dir": str(tmp_path / "run"),
            "terminal": "tmux",
            "pane_id": "%1",
            "work_dir": str(tmp_path),
            "active": True,
        },
    )

    session = load_project_session(tmp_path)
    assert session is not None
    session.update_opencode_binding(session_id="ses_abc", project_id="proj1")

    session2 = load_project_session(tmp_path)
    assert session2 is not None
    assert session2.opencode_session_id == "ses_abc"
    assert session2.opencode_project_id == "proj1"
    assert session2.opencode_session_id_filter == "ses_abc"


def test_opencode_session_legacy_session_id_as_storage_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    session_file = tmp_path / ".opencode-session"
    _write_session(
        session_file,
        {
            "session_id": "ses_legacy",
            "runtime_dir": str(tmp_path / "run"),
            "terminal": "tmux",
            "pane_id": "%1",
            "work_dir": str(tmp_path),
            "active": True,
        },
    )

    session = load_project_session(tmp_path)
    assert session is not None
    assert session.opencode_session_id == "ses_legacy"
    assert session.opencode_session_id_filter == "ses_legacy"


class _FakeTmuxBackend:
    def __init__(self) -> None:
        self.alive = set()
        self.marker_map = {}
        self.respawned = []

    def is_alive(self, pane_id: str) -> bool:
        return pane_id in self.alive

    def find_pane_by_title_marker(self, marker: str):
        return self.marker_map.get(marker) or self.marker_map.get(marker.split("-", 1)[0])

    def respawn_pane(self, pane_id: str, cmd: str, cwd: str, remain_on_exit: bool = True):
        self.respawned.append((pane_id, cmd, cwd, remain_on_exit))
        # Simulate respawn failure in this regression case.
        return None


def test_opencode_ensure_pane_does_not_trust_stale_alive_pane_without_marker(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    session_file = tmp_path / ".opencode-session"
    _write_session(
        session_file,
        {
            "session_id": "ai-123",
            "runtime_dir": str(tmp_path / "run"),
            "terminal": "tmux",
            "pane_id": "%2",
            "pane_title_marker": "CCB-OpenCode",
            "work_dir": str(tmp_path),
            "active": True,
            "start_cmd": "opencode --continue",
        },
    )

    backend = _FakeTmuxBackend()
    backend.alive = {"%2"}  # stale/reused pane id appears alive
    backend.marker_map = {}  # marker cannot be resolved
    monkeypatch.setattr(oaskd_session, "get_backend_for_session", lambda _data: backend)

    sess = load_project_session(tmp_path)
    assert sess is not None

    ok, msg = sess.ensure_pane()
    assert ok is False
    assert "Pane marker not found" in msg or "respawn failed" in msg
