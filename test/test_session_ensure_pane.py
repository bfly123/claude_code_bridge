from __future__ import annotations

import json
from pathlib import Path

import pytest

import oaskd_session


class FakeBackend:
    def __init__(self, alive_panes: dict[str, bool] | None = None, marker_map: dict[str, str] | None = None):
        self.alive = alive_panes or {}
        self.marker_map = marker_map or {}

    def is_alive(self, pane_id: str) -> bool:
        return self.alive.get(pane_id, False)

    def find_pane_by_title_marker(self, marker: str) -> str | None:
        for prefix, pane in self.marker_map.items():
            if marker.startswith(prefix) or prefix.startswith(marker):
                return pane
        return None


def test_ensure_pane_marker_rediscovers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When pane_id is dead but marker can find a new pane, ensure_pane should update and return success."""
    session_path = tmp_path / ".opencode-session"
    session_path.write_text(json.dumps({
        "session_id": "test-session",
        "terminal": "tmux",
        "pane_id": "%1",  # This pane is dead
        "pane_title_marker": "CCB-opencode-test",
        "runtime_dir": str(tmp_path),
        "work_dir": str(tmp_path),
        "active": True,
        "start_cmd": "sleep 1",
    }), encoding="utf-8")

    # %1 is dead, but marker finds %2 which is alive
    fake_backend = FakeBackend(
        alive_panes={"%1": False, "%2": True},
        marker_map={"CCB-opencode": "%2"}
    )
    monkeypatch.setattr(oaskd_session, "get_backend_for_session", lambda data: fake_backend)

    sess = oaskd_session.load_project_session(tmp_path)
    assert sess is not None

    ok, pane = sess.ensure_pane()
    assert ok is True
    assert pane == "%2"

    # Verify pane_id was written back
    data = json.loads(session_path.read_text(encoding="utf-8"))
    assert data["pane_id"] == "%2"


def test_ensure_pane_already_alive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When pane_id is already alive, ensure_pane should return success immediately."""
    session_path = tmp_path / ".opencode-session"
    session_path.write_text(json.dumps({
        "session_id": "test-session",
        "terminal": "tmux",
        "pane_id": "%1",
        "pane_title_marker": "CCB-opencode-test",
        "work_dir": str(tmp_path),
        "active": True,
    }), encoding="utf-8")

    fake_backend = FakeBackend(alive_panes={"%1": True})
    monkeypatch.setattr(oaskd_session, "get_backend_for_session", lambda data: fake_backend)

    sess = oaskd_session.load_project_session(tmp_path)
    assert sess is not None

    ok, pane = sess.ensure_pane()
    assert ok is True
    assert pane == "%1"


def test_ensure_pane_no_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When backend is not available, ensure_pane should return failure."""
    session_path = tmp_path / ".opencode-session"
    session_path.write_text(json.dumps({
        "session_id": "test-session",
        "terminal": "unknown",
        "pane_id": "%1",
        "work_dir": str(tmp_path),
        "active": True,
    }), encoding="utf-8")

    monkeypatch.setattr(oaskd_session, "get_backend_for_session", lambda data: None)

    sess = oaskd_session.load_project_session(tmp_path)
    assert sess is not None

    ok, msg = sess.ensure_pane()
    assert ok is False
    assert "backend" in msg.lower()


def test_ensure_pane_dead_no_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When pane is dead and no marker can find it, ensure_pane should return failure."""
    session_path = tmp_path / ".opencode-session"
    session_path.write_text(json.dumps({
        "session_id": "test-session",
        "terminal": "wezterm",  # Not tmux, so no respawn
        "pane_id": "%1",
        "pane_title_marker": "CCB-opencode-test",
        "work_dir": str(tmp_path),
        "active": True,
    }), encoding="utf-8")

    fake_backend = FakeBackend(alive_panes={"%1": False}, marker_map={})
    monkeypatch.setattr(oaskd_session, "get_backend_for_session", lambda data: fake_backend)

    sess = oaskd_session.load_project_session(tmp_path)
    assert sess is not None

    ok, msg = sess.ensure_pane()
    assert ok is False
    assert "not alive" in msg.lower()
