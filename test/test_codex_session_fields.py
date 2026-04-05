from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from provider_backends.codex.comm import CodexCommunicator
from provider_backends.codex.comm_runtime.communicator_state import ensure_log_reader
from provider_backends.codex.comm_runtime import load_codex_session_info
from provider_backends.codex.bridge import CodexBindingTracker
from provider_backends.codex.session import CodexProjectSession


def test_codex_session_update_binding_persists_resume_fields(tmp_path: Path) -> None:
    cfg = tmp_path / ".ccb"
    cfg.mkdir(parents=True, exist_ok=True)
    session_file = cfg / ".codex-session"
    session_file.write_text(
        json.dumps(
            {
                "start_cmd": "export CODEX_RUNTIME_DIR=/tmp/demo; codex -c disable_paste_burst=true",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    session = CodexProjectSession(
        session_file=session_file,
        data=json.loads(session_file.read_text(encoding="utf-8")),
    )
    log_path = tmp_path / "123e4567-e89b-12d3-a456-426614174000.jsonl"
    log_path.write_text("", encoding="utf-8")

    session.update_codex_log_binding(log_path=str(log_path), session_id="123e4567-e89b-12d3-a456-426614174000")

    data = json.loads(session_file.read_text(encoding="utf-8"))
    assert data["codex_session_path"] == str(log_path)
    assert data["codex_session_id"] == "123e4567-e89b-12d3-a456-426614174000"
    assert data["codex_start_cmd"] == (
        "export CODEX_RUNTIME_DIR=/tmp/demo; "
        "codex -c disable_paste_burst=true resume 123e4567-e89b-12d3-a456-426614174000"
    )
    assert data["start_cmd"] == data["codex_start_cmd"]


def test_codex_comm_remember_updates_session_file_and_runtime_info(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / ".ccb"
    cfg.mkdir(parents=True, exist_ok=True)
    session_file = cfg / ".codex-session"
    session_file.write_text(
        json.dumps(
            {
                "active": True,
                "start_cmd": "export CODEX_RUNTIME_DIR=/tmp/demo; codex -c disable_paste_burst=true",
            }
        ),
        encoding="utf-8",
    )

    log_path = tmp_path / "123e4567-e89b-12d3-a456-426614174001.jsonl"
    log_path.write_text("", encoding="utf-8")

    comm = CodexCommunicator.__new__(CodexCommunicator)
    comm.project_session_file = str(session_file)
    comm.session_info = {"work_dir": str(tmp_path)}
    comm.ccb_session_id = "ccb-session-id"
    comm.terminal = "tmux"
    comm.pane_id = "%1"
    comm.pane_title_marker = "CCB-codex-demo"

    class _Reader:
        def __init__(self) -> None:
            self.preferred = None

        def set_preferred_log(self, path: Path) -> None:
            self.preferred = path

        def current_log_path(self):
            return None

    reader = _Reader()
    comm._log_reader = reader
    monkeypatch.setattr("provider_backends.codex.comm.publish_registry_binding", lambda **kwargs: None)

    comm._remember_codex_session(log_path)

    data = json.loads(session_file.read_text(encoding="utf-8"))
    assert data["codex_session_path"] == str(log_path)
    assert data["codex_session_id"] == "123e4567-e89b-12d3-a456-426614174001"
    assert data["codex_start_cmd"] == (
        "export CODEX_RUNTIME_DIR=/tmp/demo; "
        "codex -c disable_paste_burst=true resume 123e4567-e89b-12d3-a456-426614174001"
    )
    assert data["start_cmd"] == data["codex_start_cmd"]
    assert comm.session_info["codex_session_path"] == str(log_path)
    assert comm.session_info["codex_session_id"] == "123e4567-e89b-12d3-a456-426614174001"
    assert comm.session_info["start_cmd"] == data["start_cmd"]
    assert reader.preferred == log_path


def test_load_codex_session_info_prefers_project_session_binding_over_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_file = tmp_path / ".ccb" / ".codex-session"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    project_log = tmp_path / "logs" / "project-session.jsonl"
    project_log.parent.mkdir(parents=True, exist_ok=True)
    project_log.write_text("", encoding="utf-8")
    session_file.write_text(
        json.dumps(
            {
                "codex_session_path": str(project_log),
                "codex_session_id": "project-session-id",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    registry_dir = tmp_path / ".home" / ".ccb" / "run"
    registry_dir.mkdir(parents=True, exist_ok=True)
    (registry_dir / "ccb-session-env-session.json").write_text(
        json.dumps(
            {
                "ccb_session_id": "env-session",
                "codex_session_path": str(tmp_path / "logs" / "registry-session.jsonl"),
                "codex_session_id": "registry-session-id",
                "updated_at": 4102444800,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    input_fifo = runtime_dir / "codex.pipe"
    input_fifo.write_text("", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path / ".home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / ".home"))
    monkeypatch.setenv("CCB_SESSION_ID", "env-session")
    monkeypatch.setenv("CODEX_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("CODEX_INPUT_FIFO", str(input_fifo))

    info = load_codex_session_info(session_finder=lambda: session_file)

    assert info is not None
    assert info["codex_session_path"] == str(project_log)
    assert info["codex_session_id"] == "project-session-id"
    assert info["_session_file"] == str(session_file)


def test_codex_binding_tracker_refreshes_session_from_workdir_scoped_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_root = tmp_path / ".codex" / "sessions"
    log_dir = session_root / "2026" / "04" / "03"
    log_dir.mkdir(parents=True, exist_ok=True)
    session_id = "123e4567-e89b-12d3-a456-426614174099"
    log_path = log_dir / f"rollout-2026-04-03T23-05-25-{session_id}.jsonl"
    work_dir = tmp_path / ".ccb" / "workspaces" / "agent1"
    work_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-04-03T15:05:31.738Z",
                "type": "session_meta",
                "payload": {
                    "id": session_id,
                    "cwd": str(work_dir),
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    session_file = tmp_path / ".ccb" / ".codex-agent1-session"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(
        json.dumps(
            {
                "work_dir": str(work_dir),
                "start_cmd": "export CODEX_RUNTIME_DIR=/tmp/demo; codex -c disable_paste_burst=true",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("CCB_SESSION_FILE", str(session_file))
    monkeypatch.setenv("CODEX_SESSION_ROOT", str(session_root))

    tracker = CodexBindingTracker(tmp_path / "runtime")

    assert tracker.refresh_once() is True

    data = json.loads(session_file.read_text(encoding="utf-8"))
    assert data["codex_session_path"] == str(log_path)
    assert data["codex_session_id"] == session_id
    assert data["codex_start_cmd"].endswith(f"resume {session_id}")
    assert data["start_cmd"] == data["codex_start_cmd"]


def test_codex_binding_tracker_can_follow_rotated_workspace_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_root = tmp_path / ".codex" / "sessions"
    log_dir = session_root / "2026" / "04" / "04"
    log_dir.mkdir(parents=True, exist_ok=True)
    work_dir = tmp_path / ".ccb" / "workspaces" / "agent1"
    work_dir.mkdir(parents=True, exist_ok=True)
    old_session_id = "123e4567-e89b-12d3-a456-426614174111"
    new_session_id = "123e4567-e89b-12d3-a456-426614174222"
    old_log = log_dir / f"rollout-2026-04-04T10-20-26-{old_session_id}.jsonl"
    new_log = log_dir / f"rollout-2026-04-04T10-39-16-{new_session_id}.jsonl"
    meta_old = json.dumps(
        {
            "timestamp": "2026-04-04T10:20:26.000Z",
            "type": "session_meta",
            "payload": {
                "id": old_session_id,
                "cwd": str(work_dir),
            },
        },
        ensure_ascii=False,
    )
    meta_new = json.dumps(
        {
            "timestamp": "2026-04-04T10:39:16.000Z",
            "type": "session_meta",
            "payload": {
                "id": new_session_id,
                "cwd": str(work_dir),
            },
        },
        ensure_ascii=False,
    )
    old_log.write_text(meta_old + "\n", encoding="utf-8")
    new_log.write_text(meta_new + "\n", encoding="utf-8")
    old_mtime = old_log.stat().st_mtime
    new_mtime = new_log.stat().st_mtime
    old_log.touch()
    os.utime(old_log, (old_mtime - 30.0, old_mtime - 30.0))
    os.utime(new_log, (new_mtime + 30.0, new_mtime + 30.0))

    session_file = tmp_path / ".ccb" / ".codex-agent1-session"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(
        json.dumps(
            {
                "work_dir": str(work_dir),
                "codex_session_path": str(old_log),
                "codex_session_id": old_session_id,
                "start_cmd": "export CODEX_RUNTIME_DIR=/tmp/demo; codex -c disable_paste_burst=true",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("CCB_SESSION_FILE", str(session_file))
    monkeypatch.setenv("CODEX_SESSION_ROOT", str(session_root))

    tracker = CodexBindingTracker(tmp_path / "runtime")

    assert tracker.refresh_once() is True

    data = json.loads(session_file.read_text(encoding="utf-8"))
    assert data["codex_session_path"] == str(new_log)
    assert data["codex_session_id"] == new_session_id
    assert data["codex_start_cmd"].endswith(f"resume {new_session_id}")
    assert data["start_cmd"] == data["codex_start_cmd"]


def test_codex_comm_live_reader_uses_workspace_follow_mode(tmp_path: Path) -> None:
    comm = CodexCommunicator.__new__(CodexCommunicator)
    comm.session_info = {
        "codex_session_path": str(tmp_path / "old.jsonl"),
        "codex_session_id": "old-session-id",
        "work_dir": str(tmp_path / "repo"),
    }
    comm._log_reader = None
    comm._log_reader_primed = True

    captured: dict[str, object] = {}

    class FakeReader:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    ensure_log_reader(comm, log_reader_cls=FakeReader)

    assert captured["log_path"] == str(tmp_path / "old.jsonl")
    assert captured["session_id_filter"] == "old-session-id"
    assert captured["work_dir"] == tmp_path / "repo"
    assert captured["follow_workspace_sessions"] is True
