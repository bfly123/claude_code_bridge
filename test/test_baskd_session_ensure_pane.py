from __future__ import annotations

import json
from pathlib import Path

import pytest

import baskd_session


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


def test_baskd_ensure_pane_respawns_dead_pane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When pane is dead, ensure_pane should respawn it and update session file."""
    session_path = tmp_path / ".codebuddy-session"
    session_path.write_text(
        json.dumps({
            "session_id": "test-session",
            "terminal": "tmux",
            "pane_id": "%1",
            "pane_title_marker": "CCB-codebuddy-test",
            "runtime_dir": str(tmp_path),
            "work_dir": str(tmp_path),
            "active": True,
            "start_cmd": "codebuddy",
        }),
        encoding="utf-8",
    )

    backend = FakeTmuxBackend()
    backend.alive = {"%1": False, "%2": False}
    backend.marker_map = {"CCB-codebuddy": "%2"}
    monkeypatch.setattr(baskd_session, "get_backend_for_session", lambda data: backend)

    sess = baskd_session.load_project_session(tmp_path)
    assert sess is not None

    ok, pane = sess.ensure_pane()
    assert ok is True
    assert pane == "%2"
    assert "%2" in backend.respawned

    data = json.loads(session_path.read_text(encoding="utf-8"))
    assert data["pane_id"] == "%2"


def test_baskd_ensure_pane_already_alive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When pane is already alive, ensure_pane should return success immediately."""
    session_path = tmp_path / ".codebuddy-session"
    session_path.write_text(
        json.dumps({
            "session_id": "test-session",
            "terminal": "tmux",
            "pane_id": "%1",
            "pane_title_marker": "CCB-codebuddy-test",
            "work_dir": str(tmp_path),
            "active": True,
        }),
        encoding="utf-8",
    )

    backend = FakeTmuxBackend()
    backend.alive = {"%1": True}
    monkeypatch.setattr(baskd_session, "get_backend_for_session", lambda data: backend)

    sess = baskd_session.load_project_session(tmp_path)
    assert sess is not None

    ok, pane = sess.ensure_pane()
    assert ok is True
    assert pane == "%1"
    assert backend.respawned == []  # No respawn needed


def test_baskd_ensure_pane_marker_rediscover(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When original pane is dead but marker finds alive pane, should update pane_id."""
    session_path = tmp_path / ".codebuddy-session"
    session_path.write_text(
        json.dumps({
            "session_id": "test-session",
            "terminal": "tmux",
            "pane_id": "%1",
            "pane_title_marker": "CCB-codebuddy-test",
            "work_dir": str(tmp_path),
            "active": True,
        }),
        encoding="utf-8",
    )

    backend = FakeTmuxBackend()
    backend.alive = {"%1": False, "%2": True}  # %2 is alive
    backend.marker_map = {"CCB-codebuddy": "%2"}
    monkeypatch.setattr(baskd_session, "get_backend_for_session", lambda data: backend)

    sess = baskd_session.load_project_session(tmp_path)
    assert sess is not None

    ok, pane = sess.ensure_pane()
    assert ok is True
    assert pane == "%2"
    assert backend.respawned == []  # No respawn needed, just rediscovered

    data = json.loads(session_path.read_text(encoding="utf-8"))
    assert data["pane_id"] == "%2"


def test_baskd_load_session_returns_none_for_inactive(tmp_path: Path) -> None:
    """Inactive sessions should return None."""
    session_path = tmp_path / ".codebuddy-session"
    session_path.write_text(
        json.dumps({
            "session_id": "test-session",
            "terminal": "tmux",
            "pane_id": "%1",
            "work_dir": str(tmp_path),
            "active": False,
        }),
        encoding="utf-8",
    )

    sess = baskd_session.load_project_session(tmp_path)
    assert sess is None


def test_baskd_load_session_returns_none_for_missing_file(tmp_path: Path) -> None:
    """Missing session file should return None."""
    sess = baskd_session.load_project_session(tmp_path)
    assert sess is None


def test_baskd_compute_session_key_prefix(tmp_path: Path) -> None:
    """Session key should use 'codebuddy:' prefix."""
    session_path = tmp_path / ".codebuddy-session"
    session_path.write_text(
        json.dumps({
            "session_id": "test-session",
            "terminal": "tmux",
            "pane_id": "%1",
            "work_dir": str(tmp_path),
            "active": True,
        }),
        encoding="utf-8",
    )

    sess = baskd_session.load_project_session(tmp_path)
    assert sess is not None

    key = baskd_session.compute_session_key(sess)
    assert key.startswith("codebuddy:")
