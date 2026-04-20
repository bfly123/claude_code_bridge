from __future__ import annotations

import json
from pathlib import Path

import pytest

import provider_backends.gemini.session as gemini_session


class FakeTmuxBackend:
    def __init__(self) -> None:
        self.alive: dict[str, bool] = {}
        self.crash_logs: list[tuple[str, str]] = []
        self.respawned: list[str] = []
        self.marker_map: dict[str, str] = {}

    def is_alive(self, pane_id: str) -> bool:
        return bool(self.alive.get(pane_id, False))

    def find_pane_by_title_marker(self, marker: str) -> str | None:
        for prefix, pane in self.marker_map.items():
            if marker.startswith(prefix) or prefix.startswith(marker):
                return pane
        return None

    def save_crash_log(self, pane_id: str, crash_log_path: str, *, lines: int = 1000) -> None:
        self.crash_logs.append((pane_id, crash_log_path))

    def respawn_pane(self, pane_id: str, *, cmd: str, cwd: str | None = None,
                     stderr_log_path: str | None = None, remain_on_exit: bool = True) -> None:
        self.respawned.append(pane_id)
        self.alive[pane_id] = True


def test_gemini_ensure_pane_respawns_dead_pane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When pane is dead, ensure_pane should respawn it and update session file."""
    session_path = tmp_path / ".gemini-session"
    session_path.write_text(
        json.dumps({
            "ccb_session_id": "test-session",
            "terminal": "tmux",
            "pane_id": "%1",
            "pane_title_marker": "CCB-gemini-test",
            "runtime_dir": str(tmp_path),
            "work_dir": str(tmp_path),
            "active": True,
            "start_cmd": "gemini-cli",
        }),
        encoding="utf-8",
    )

    backend = FakeTmuxBackend()
    backend.alive = {"%1": False, "%2": False}
    monkeypatch.setattr(gemini_session, "get_backend_for_session", lambda data: backend)

    sess = gemini_session.load_project_session(tmp_path)
    assert sess is not None

    ok, pane = sess.ensure_pane()
    assert ok is True
    assert pane == "%1"
    assert backend.respawned == ["%1"]

    data = json.loads(session_path.read_text(encoding="utf-8"))
    assert data["pane_id"] == "%1"


def test_gemini_ensure_pane_already_alive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When pane is already alive, ensure_pane should return success immediately."""
    session_path = tmp_path / ".gemini-session"
    session_path.write_text(
        json.dumps({
            "ccb_session_id": "test-session",
            "terminal": "tmux",
            "pane_id": "%1",
            "pane_title_marker": "CCB-gemini-test",
            "work_dir": str(tmp_path),
            "active": True,
        }),
        encoding="utf-8",
    )

    backend = FakeTmuxBackend()
    backend.alive = {"%1": True}
    monkeypatch.setattr(gemini_session, "get_backend_for_session", lambda data: backend)

    sess = gemini_session.load_project_session(tmp_path)
    assert sess is not None

    ok, pane = sess.ensure_pane()
    assert ok is True
    assert pane == "%1"
    assert backend.respawned == []


def test_gemini_ensure_pane_does_not_rediscover_different_pane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session_path = tmp_path / ".gemini-session"
    session_path.write_text(
        json.dumps({
            "ccb_session_id": "test-session",
            "terminal": "tmux",
            "pane_id": "%1",
            "pane_title_marker": "CCB-gemini-test",
            "work_dir": str(tmp_path),
            "active": True,
        }),
        encoding="utf-8",
    )

    backend = FakeTmuxBackend()
    backend.alive = {"%1": False, "%2": True}
    backend.marker_map = {"CCB-gemini": "%2"}
    monkeypatch.setattr(gemini_session, "get_backend_for_session", lambda data: backend)

    sess = gemini_session.load_project_session(tmp_path)
    assert sess is not None

    ok, msg = sess.ensure_pane()
    assert ok is False
    assert "not alive" in msg.lower()
    assert backend.respawned == []

    data = json.loads(session_path.read_text(encoding="utf-8"))
    assert data["pane_id"] == "%1"
