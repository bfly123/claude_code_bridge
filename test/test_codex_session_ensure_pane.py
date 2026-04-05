from __future__ import annotations

import json
from pathlib import Path

import pytest

import provider_backends.codex.session as codex_session


class FakeTmuxBackend:
    def __init__(self) -> None:
        self.alive: dict[str, bool] = {}
        self.exists: dict[str, bool] = {}
        self.crash_logs: list[tuple[str, str]] = []
        self.respawned: list[str] = []
        self.marker_map: dict[str, str] = {}
        self.created: list[tuple[str, str]] = []
        self.titles: list[tuple[str, str]] = []
        self.options: list[tuple[str, str, str]] = []

    def is_alive(self, pane_id: str) -> bool:
        return bool(self.alive.get(pane_id, False))

    def pane_exists(self, pane_id: str) -> bool:
        return bool(self.exists.get(pane_id, pane_id in self.alive))

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

    def create_pane(self, cmd: str, cwd: str, direction: str = "right", percent: int = 50, parent_pane: str | None = None) -> str:
        del direction, percent, parent_pane
        self.created.append((cmd, cwd))
        self.alive["%99"] = True
        return "%99"

    def set_pane_title(self, pane_id: str, title: str) -> None:
        self.titles.append((pane_id, title))

    def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
        self.options.append((pane_id, name, value))


def test_codex_ensure_pane_respawns_dead_pane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When pane is dead, ensure_pane should respawn it and update session file."""
    session_path = tmp_path / ".codex-session"
    session_path.write_text(
        json.dumps({
            "ccb_session_id": "test-session",
            "terminal": "tmux",
            "pane_id": "%1",
            "pane_title_marker": "CCB-codex-test",
            "runtime_dir": str(tmp_path),
            "work_dir": str(tmp_path),
            "active": True,
            "codex_start_cmd": "codex resume deadbeef",
        }),
        encoding="utf-8",
    )

    backend = FakeTmuxBackend()
    backend.alive = {"%1": False, "%2": False}
    monkeypatch.setattr(codex_session, "get_backend_for_session", lambda data: backend)
    monkeypatch.setattr(codex_session, "find_project_session_file", lambda work_dir, instance=None: session_path)

    sess = codex_session.load_project_session(tmp_path)
    assert sess is not None

    ok, pane = sess.ensure_pane()
    assert ok is True
    assert pane == "%1"
    assert backend.respawned == ["%1"]

    data = json.loads(session_path.read_text(encoding="utf-8"))
    assert data["pane_id"] == "%1"


def test_codex_ensure_pane_prefers_full_start_cmd_when_legacy_codex_resume_cmd_is_bare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_path = tmp_path / ".codex-session"
    session_path.write_text(
        json.dumps(
            {
                "ccb_session_id": "test-session",
                "terminal": "tmux",
                "pane_id": "%1",
                "pane_title_marker": "CCB-codex-test",
                "runtime_dir": str(tmp_path),
                "work_dir": str(tmp_path),
                "active": True,
                "codex_session_id": "deadbeef",
                "start_cmd": "export CODEX_RUNTIME_DIR=/tmp/demo; codex -c disable_paste_burst=true",
                "codex_start_cmd": "codex resume deadbeef",
            }
        ),
        encoding="utf-8",
    )

    calls: list[tuple[str, str | None]] = []
    backend = FakeTmuxBackend()
    backend.alive = {"%1": False}

    def _respawn(pane_id: str, *, cmd: str, cwd: str | None = None,
                 stderr_log_path: str | None = None, remain_on_exit: bool = True) -> None:
        del stderr_log_path, remain_on_exit
        calls.append((cmd, cwd))
        backend.alive[pane_id] = True

    backend.respawn_pane = _respawn  # type: ignore[method-assign]
    monkeypatch.setattr(codex_session, "get_backend_for_session", lambda data: backend)
    monkeypatch.setattr(codex_session, "find_project_session_file", lambda work_dir, instance=None: session_path)

    sess = codex_session.load_project_session(tmp_path)
    assert sess is not None

    ok, pane = sess.ensure_pane()
    assert ok is True
    assert pane == "%1"
    assert calls == [("export CODEX_RUNTIME_DIR=/tmp/demo; codex -c disable_paste_burst=true resume deadbeef", str(tmp_path))]


def test_codex_ensure_pane_already_alive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When pane is already alive, ensure_pane should return success immediately."""
    session_path = tmp_path / ".codex-session"
    session_path.write_text(
        json.dumps({
            "ccb_session_id": "test-session",
            "terminal": "tmux",
            "pane_id": "%1",
            "pane_title_marker": "CCB-codex-test",
            "work_dir": str(tmp_path),
            "active": True,
        }),
        encoding="utf-8",
    )

    backend = FakeTmuxBackend()
    backend.alive = {"%1": True}
    monkeypatch.setattr(codex_session, "get_backend_for_session", lambda data: backend)
    monkeypatch.setattr(codex_session, "find_project_session_file", lambda work_dir, instance=None: session_path)

    sess = codex_session.load_project_session(tmp_path)
    assert sess is not None

    ok, pane = sess.ensure_pane()
    assert ok is True
    assert pane == "%1"
    assert backend.respawned == []  # No respawn needed


def test_codex_ensure_pane_does_not_rediscover_different_pane_without_start_cmd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_path = tmp_path / ".codex-session"
    session_path.write_text(
        json.dumps({
            "ccb_session_id": "test-session",
            "terminal": "tmux",
            "pane_id": "%1",
            "pane_title_marker": "CCB-codex-test",
            "work_dir": str(tmp_path),
            "active": True,
        }),
        encoding="utf-8",
    )

    backend = FakeTmuxBackend()
    backend.alive = {"%1": False, "%2": True}  # %2 is alive
    backend.marker_map = {"CCB-codex": "%2"}
    monkeypatch.setattr(codex_session, "get_backend_for_session", lambda data: backend)
    monkeypatch.setattr(codex_session, "find_project_session_file", lambda work_dir, instance=None: session_path)

    sess = codex_session.load_project_session(tmp_path)
    assert sess is not None

    ok, msg = sess.ensure_pane()
    assert ok is False
    assert "not alive" in msg.lower()
    assert backend.respawned == []

    data = json.loads(session_path.read_text(encoding="utf-8"))
    assert data["pane_id"] == "%1"


def test_codex_ensure_pane_respawns_recorded_pane_even_if_other_pane_is_alive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_path = tmp_path / ".codex-session"
    session_path.write_text(
        json.dumps({
            "ccb_session_id": "test-session",
            "terminal": "tmux",
            "pane_id": "%1",
            "pane_title_marker": "CCB-codex",
            "ccb_project_id": "12345678abcdef00",
            "runtime_dir": str(tmp_path),
            "work_dir": str(tmp_path),
            "active": True,
            "codex_start_cmd": "codex resume deadbeef",
        }),
        encoding="utf-8",
    )

    backend = FakeTmuxBackend()
    backend.alive = {"%1": False, "%2": True}
    backend.marker_map = {"CCB-codex": "%2"}
    monkeypatch.setattr(codex_session, "get_backend_for_session", lambda data: backend)
    monkeypatch.setattr(codex_session, "find_project_session_file", lambda work_dir, instance=None: session_path)

    sess = codex_session.load_project_session(tmp_path)
    assert sess is not None

    ok, pane = sess.ensure_pane()
    assert ok is True
    assert pane == "%1"
    assert backend.respawned == ["%1"]

    data = json.loads(session_path.read_text(encoding="utf-8"))
    assert data["pane_id"] == "%1"


def test_codex_ensure_pane_creates_new_pane_when_respawn_target_is_gone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session_path = tmp_path / ".codex-session"
    session_path.write_text(
        json.dumps({
            "ccb_session_id": "test-session",
            "agent_name": "agent1",
            "ccb_project_id": "12345678abcdef00",
            "terminal": "tmux",
            "pane_id": "%1",
            "tmux_session": "%1",
            "pane_title_marker": "CCB-agent1-12345678",
            "runtime_dir": str(tmp_path),
            "work_dir": str(tmp_path),
            "active": True,
            "codex_start_cmd": "codex resume deadbeef",
        }),
        encoding="utf-8",
    )

    backend = FakeTmuxBackend()
    backend.alive = {"%1": False}
    backend.exists = {"%1": True}

    def _respawn_fail(pane_id: str, *, cmd: str, cwd: str | None = None,
                      stderr_log_path: str | None = None, remain_on_exit: bool = True) -> None:
        raise RuntimeError("respawn failed")

    backend.respawn_pane = _respawn_fail  # type: ignore[method-assign]
    monkeypatch.setattr(codex_session, "get_backend_for_session", lambda data: backend)
    monkeypatch.setattr(codex_session, "find_project_session_file", lambda work_dir, instance=None: session_path)

    sess = codex_session.load_project_session(tmp_path)
    assert sess is not None

    ok, pane = sess.ensure_pane()
    assert ok is True
    assert pane == "%99"
    assert backend.created == [("codex resume deadbeef", str(tmp_path))]
    assert backend.titles == [("%99", "agent1")]
    assert ("%99", "@ccb_agent", "agent1") in backend.options
    assert ("%99", "@ccb_project_id", "12345678abcdef00") in backend.options

    data = json.loads(session_path.read_text(encoding="utf-8"))
    assert data["pane_id"] == "%99"
    assert data["tmux_session"] == "%99"


def test_codex_ensure_pane_skips_respawn_for_missing_pane_and_creates_new_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session_path = tmp_path / ".codex-session"
    session_path.write_text(
        json.dumps({
            "ccb_session_id": "test-session",
            "agent_name": "agent1",
            "ccb_project_id": "12345678abcdef00",
            "terminal": "tmux",
            "pane_id": "%1",
            "tmux_session": "%1",
            "pane_title_marker": "CCB-agent1-12345678",
            "runtime_dir": str(tmp_path),
            "work_dir": str(tmp_path),
            "active": True,
            "codex_start_cmd": "codex resume deadbeef",
        }),
        encoding="utf-8",
    )

    backend = FakeTmuxBackend()
    backend.alive = {"%1": False}
    backend.exists = {"%1": False}
    monkeypatch.setattr(codex_session, "get_backend_for_session", lambda data: backend)
    monkeypatch.setattr(codex_session, "find_project_session_file", lambda work_dir, instance=None: session_path)

    sess = codex_session.load_project_session(tmp_path)
    assert sess is not None

    ok, pane = sess.ensure_pane()
    assert ok is True
    assert pane == "%99"
    assert backend.respawned == []
    assert backend.crash_logs == []
    assert backend.created == [("codex resume deadbeef", str(tmp_path))]
