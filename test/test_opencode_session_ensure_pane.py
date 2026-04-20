from __future__ import annotations

import json
from pathlib import Path

import pytest

import provider_backends.opencode.session as opencode_session


class FakeBackend:
    def __init__(self, alive_panes: dict[str, bool] | None = None, marker_map: dict[str, str] | None = None):
        self.alive = alive_panes or {}
        self.marker_map = marker_map or {}
        self.exists = {pane_id: True for pane_id in self.alive}
        self.respawned: list[str] = []
        self.crash_logs: list[tuple[str, str]] = []

    def is_alive(self, pane_id: str) -> bool:
        return self.alive.get(pane_id, False)

    def pane_exists(self, pane_id: str) -> bool:
        return self.exists.get(pane_id, pane_id in self.alive)

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


def test_ensure_pane_respawns_recorded_pane_without_marker_rebind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When pane_id is dead, ensure_pane should revive the recorded pane."""
    session_path = tmp_path / ".opencode-session"
    session_path.write_text(json.dumps({
        "ccb_session_id": "test-session",
        "terminal": "tmux",
        "pane_id": "%1",  # This pane is dead
        "pane_title_marker": "CCB-opencode-test",
        "runtime_dir": str(tmp_path),
        "work_dir": str(tmp_path),
        "active": True,
        "start_cmd": "sleep 1",
    }), encoding="utf-8")

    fake_backend = FakeBackend(
        alive_panes={"%1": False, "%2": True},
        marker_map={"CCB-opencode": "%2"}
    )
    monkeypatch.setattr(opencode_session, "get_backend_for_session", lambda data: fake_backend)

    sess = opencode_session.load_project_session(tmp_path)
    assert sess is not None

    ok, pane = sess.ensure_pane()
    assert ok is True
    assert pane == "%1"
    assert fake_backend.respawned == ["%1"]

    data = json.loads(session_path.read_text(encoding="utf-8"))
    assert data["pane_id"] == "%1"


def test_ensure_pane_already_alive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When pane_id is already alive, ensure_pane should return success immediately."""
    session_path = tmp_path / ".opencode-session"
    session_path.write_text(json.dumps({
        "ccb_session_id": "test-session",
        "terminal": "tmux",
        "pane_id": "%1",
        "pane_title_marker": "CCB-opencode-test",
        "work_dir": str(tmp_path),
        "active": True,
    }), encoding="utf-8")

    fake_backend = FakeBackend(alive_panes={"%1": True})
    monkeypatch.setattr(opencode_session, "get_backend_for_session", lambda data: fake_backend)

    sess = opencode_session.load_project_session(tmp_path)
    assert sess is not None

    ok, pane = sess.ensure_pane()
    assert ok is True
    assert pane == "%1"


def test_ensure_pane_no_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When backend is not available, ensure_pane should return failure."""
    session_path = tmp_path / ".opencode-session"
    session_path.write_text(json.dumps({
        "ccb_session_id": "test-session",
        "terminal": "unknown",
        "pane_id": "%1",
        "work_dir": str(tmp_path),
        "active": True,
    }), encoding="utf-8")

    monkeypatch.setattr(opencode_session, "get_backend_for_session", lambda data: None)

    sess = opencode_session.load_project_session(tmp_path)
    assert sess is not None

    ok, msg = sess.ensure_pane()
    assert ok is False
    assert "backend" in msg.lower()


def test_ensure_pane_dead_no_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When pane is dead and no marker can find it, ensure_pane should return failure."""
    session_path = tmp_path / ".opencode-session"
    session_path.write_text(json.dumps({
        "ccb_session_id": "test-session",
        "terminal": "unknown",  # Not tmux, so no respawn
        "pane_id": "%1",
        "pane_title_marker": "CCB-opencode-test",
        "work_dir": str(tmp_path),
        "active": True,
    }), encoding="utf-8")

    fake_backend = FakeBackend(alive_panes={"%1": False}, marker_map={})
    monkeypatch.setattr(opencode_session, "get_backend_for_session", lambda data: fake_backend)

    sess = opencode_session.load_project_session(tmp_path)
    assert sess is not None

    ok, msg = sess.ensure_pane()
    assert ok is False
    assert "not alive" in msg.lower()


def test_ensure_pane_missing_tmux_target_skips_respawn_noise(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session_path = tmp_path / ".opencode-session"
    session_path.write_text(json.dumps({
        "ccb_session_id": "test-session",
        "terminal": "tmux",
        "pane_id": "%1",
        "pane_title_marker": "CCB-opencode-test",
        "runtime_dir": str(tmp_path),
        "work_dir": str(tmp_path),
        "active": True,
        "start_cmd": "sleep 1",
    }), encoding="utf-8")

    fake_backend = FakeBackend(alive_panes={"%1": False}, marker_map={})
    fake_backend.exists["%1"] = False
    monkeypatch.setattr(opencode_session, "get_backend_for_session", lambda data: fake_backend)

    sess = opencode_session.load_project_session(tmp_path)
    assert sess is not None

    ok, msg = sess.ensure_pane()
    assert ok is False
    assert "respawn failed" in msg.lower()
    assert "no longer exists" in msg.lower()
    assert fake_backend.respawned == []
    assert fake_backend.crash_logs == []
