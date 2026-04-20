from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from provider_backends.codex.comm import CodexCommunicator
from provider_backends.codex.comm_runtime.communicator_state import ensure_log_reader
from provider_backends.codex.comm_runtime import load_codex_session_info
from provider_backends.codex.comm_runtime.watchdog import handle_codex_log_event
from provider_backends.codex.bridge import CodexBindingTracker
from provider_backends.codex.session import CodexProjectSession
from provider_backends.codex.session import load_project_session


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
                "codex_session_root": str(tmp_path / ".codex" / "sessions"),
                "codex_home": str(tmp_path / ".codex"),
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
    assert info["codex_session_root"] == str(tmp_path / ".codex" / "sessions")
    assert info["codex_home"] == str(tmp_path / ".codex")
    assert info["_session_file"] == str(session_file)


def test_load_project_session_migrates_legacy_root_only_binding_to_private_home(tmp_path: Path) -> None:
    work_dir = tmp_path / "repo"
    session_dir = work_dir / ".ccb"
    legacy_root = tmp_path / "legacy-state" / "sessions"
    legacy_log = legacy_root / "2026" / "04" / "19" / "rollout-legacy-session.jsonl"
    legacy_log.parent.mkdir(parents=True, exist_ok=True)
    legacy_log.write_text("", encoding="utf-8")
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / ".codex-agent1-session"
    session_file.write_text(
        json.dumps(
            {
                "work_dir": str(work_dir),
                "codex_session_root": str(legacy_root),
                "codex_session_path": str(legacy_log),
                "codex_session_id": "legacy-session-id",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    session = load_project_session(work_dir, "agent1")

    assert session is not None
    expected_home = legacy_root.parent / "home"
    expected_root = expected_home / "sessions"
    assert session.codex_home == str(expected_home)
    assert session.codex_session_root == str(expected_root)
    payload = json.loads(session_file.read_text(encoding="utf-8"))
    assert payload["codex_home"] == str(expected_home)
    assert payload["codex_session_root"] == str(expected_root)
    assert (expected_root / "2026" / "04" / "19" / "rollout-legacy-session.jsonl").is_file()


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
                "codex_home": str(tmp_path / ".codex"),
                "codex_session_root": str(session_root),
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


def test_codex_binding_tracker_keeps_existing_bound_session_within_agent_root(
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
                "codex_home": str(tmp_path / ".codex"),
                "codex_session_root": str(session_root),
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
    assert data["codex_session_path"] == str(old_log)
    assert data["codex_session_id"] == old_session_id
    assert data["codex_start_cmd"].endswith(f"resume {old_session_id}")
    assert data["start_cmd"] == data["codex_start_cmd"]


def test_codex_binding_tracker_keeps_bound_session_when_work_dir_has_multiple_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_root = tmp_path / ".codex" / "sessions"
    log_dir = session_root / "2026" / "04" / "05"
    log_dir.mkdir(parents=True, exist_ok=True)
    work_dir = tmp_path / "repo"
    work_dir.mkdir(parents=True, exist_ok=True)
    bound_session_id = "123e4567-e89b-12d3-a456-426614174333"
    other_session_id = "123e4567-e89b-12d3-a456-426614174444"
    bound_log = log_dir / f"rollout-2026-04-05T10-20-26-{bound_session_id}.jsonl"
    newer_log = log_dir / f"rollout-2026-04-05T10-39-16-{other_session_id}.jsonl"
    meta_bound = json.dumps(
        {
            "timestamp": "2026-04-05T10:20:26.000Z",
            "type": "session_meta",
            "payload": {
                "id": bound_session_id,
                "cwd": str(work_dir),
            },
        },
        ensure_ascii=False,
    )
    meta_newer = json.dumps(
        {
            "timestamp": "2026-04-05T10:39:16.000Z",
            "type": "session_meta",
            "payload": {
                "id": other_session_id,
                "cwd": str(work_dir),
            },
        },
        ensure_ascii=False,
    )
    bound_log.write_text(meta_bound + "\n", encoding="utf-8")
    newer_log.write_text(meta_newer + "\n", encoding="utf-8")
    bound_mtime = bound_log.stat().st_mtime
    newer_mtime = newer_log.stat().st_mtime
    os.utime(bound_log, (bound_mtime - 30.0, bound_mtime - 30.0))
    os.utime(newer_log, (newer_mtime + 30.0, newer_mtime + 30.0))

    session_dir = work_dir / ".ccb"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / ".codex-agent1-session"
    session_file.write_text(
        json.dumps(
            {
                "work_dir": str(work_dir),
                "codex_home": str(tmp_path / ".codex"),
                "codex_session_root": str(session_root),
                "codex_session_path": str(bound_log),
                "codex_session_id": bound_session_id,
                "start_cmd": (
                    "export CODEX_RUNTIME_DIR=/tmp/demo; "
                    f"codex -c disable_paste_burst=true resume {bound_session_id}"
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (session_dir / ".codex-agent2-session").write_text(
        json.dumps(
            {
                "work_dir": str(work_dir),
                "codex_session_path": str(newer_log),
                "codex_session_id": other_session_id,
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
    assert data["codex_session_path"] == str(bound_log)
    assert data["codex_session_id"] == bound_session_id
    assert data["codex_start_cmd"].endswith(f"resume {bound_session_id}")


def test_codex_comm_live_reader_uses_bound_root_and_disables_workspace_follow_when_bound(tmp_path: Path) -> None:
    session_root = tmp_path / ".codex" / "sessions"
    comm = CodexCommunicator.__new__(CodexCommunicator)
    comm.session_info = {
        "codex_session_path": str(tmp_path / "old.jsonl"),
        "codex_session_id": "old-session-id",
        "codex_session_root": str(session_root),
        "work_dir": str(tmp_path / "repo"),
    }
    comm._log_reader = None
    comm._log_reader_primed = True

    captured: dict[str, object] = {}

    class FakeReader:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    ensure_log_reader(comm, log_reader_cls=FakeReader)

    assert captured["root"] == session_root
    assert captured["log_path"] == str(tmp_path / "old.jsonl")
    assert captured["session_id_filter"] == "old-session-id"
    assert captured["work_dir"] == tmp_path / "repo"
    assert captured["follow_workspace_sessions"] is False


def test_codex_comm_live_reader_disables_workspace_follow_for_ambiguous_inplace_agents(tmp_path: Path) -> None:
    work_dir = tmp_path / "repo"
    work_dir.mkdir(parents=True, exist_ok=True)
    session_dir = work_dir / ".ccb"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / ".codex-agent1-session"
    session_file.write_text(json.dumps({"work_dir": str(work_dir)}), encoding="utf-8")
    (session_dir / ".codex-agent2-session").write_text(json.dumps({"work_dir": str(work_dir)}), encoding="utf-8")

    comm = CodexCommunicator.__new__(CodexCommunicator)
    comm.session_info = {
        "codex_session_path": str(tmp_path / "old.jsonl"),
        "codex_session_id": "old-session-id",
        "codex_session_root": str(tmp_path / ".codex" / "sessions"),
        "work_dir": str(work_dir),
        "_session_file": str(session_file),
    }
    comm._log_reader = None
    comm._log_reader_primed = True

    captured: dict[str, object] = {}

    class FakeReader:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    ensure_log_reader(comm, log_reader_cls=FakeReader)

    assert captured["follow_workspace_sessions"] is False


def test_codex_comm_live_reader_enables_workspace_follow_for_unbound_session(tmp_path: Path) -> None:
    session_root = tmp_path / ".codex" / "sessions"
    comm = CodexCommunicator.__new__(CodexCommunicator)
    comm.session_info = {
        "codex_session_root": str(session_root),
        "work_dir": str(tmp_path / "repo"),
    }
    comm._log_reader = None
    comm._log_reader_primed = True

    captured: dict[str, object] = {}

    class FakeReader:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    ensure_log_reader(comm, log_reader_cls=FakeReader)

    assert captured["root"] == session_root
    assert captured["follow_workspace_sessions"] is True


def test_codex_log_reader_default_root_uses_current_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from provider_backends.codex.comm import CodexLogReader

    session_root = tmp_path / ".codex" / "sessions"
    monkeypatch.setenv("CODEX_SESSION_ROOT", str(session_root))

    reader = CodexLogReader()

    assert reader.root == session_root


def test_codex_watchdog_ignores_log_outside_bound_session_root(tmp_path: Path) -> None:
    work_dir = tmp_path / "repo"
    work_dir.mkdir(parents=True, exist_ok=True)
    bound_root = tmp_path / "managed" / "sessions"
    foreign_root = tmp_path / "foreign" / "sessions"
    foreign_log = foreign_root / "2026" / "04" / "19" / "rollout-foreign-session.jsonl"
    foreign_log.parent.mkdir(parents=True, exist_ok=True)
    foreign_log.write_text("", encoding="utf-8")

    calls: list[tuple[str, str | None]] = []

    class _Session:
        data = {
            "work_dir": str(work_dir),
            "codex_session_root": str(bound_root),
            "codex_session_path": str(bound_root / "2026" / "04" / "19" / "rollout-bound-session.jsonl"),
            "codex_session_id": "bound-session",
        }
        codex_session_path = data["codex_session_path"]
        codex_session_id = data["codex_session_id"]

        def update_codex_log_binding(self, *, log_path: str | None, session_id: str | None) -> None:
            calls.append((str(log_path), session_id))

    handle_codex_log_event(
        foreign_log,
        cwd_extractor=lambda path: str(work_dir),
        session_resolver=lambda cwd: (work_dir / ".ccb" / ".codex-agent1-session", "agent1"),
        session_loader=lambda cwd, instance: _Session(),
        session_id_extractor=lambda path: "foreign-session",
    )

    assert calls == []


def test_codex_watchdog_keeps_bound_session_from_rebinding_to_newer_log(tmp_path: Path) -> None:
    work_dir = tmp_path / "repo"
    work_dir.mkdir(parents=True, exist_ok=True)
    session_root = tmp_path / "managed" / "sessions"
    old_log = session_root / "2026" / "04" / "19" / "rollout-old-session.jsonl"
    new_log = session_root / "2026" / "04" / "19" / "rollout-new-session.jsonl"
    old_log.parent.mkdir(parents=True, exist_ok=True)
    old_log.write_text("", encoding="utf-8")
    new_log.write_text("", encoding="utf-8")

    calls: list[tuple[str, str | None]] = []

    class _Session:
        data = {
            "work_dir": str(work_dir),
            "codex_session_root": str(session_root),
            "codex_session_path": str(old_log),
            "codex_session_id": "old-session",
        }
        codex_session_path = data["codex_session_path"]
        codex_session_id = data["codex_session_id"]

        def update_codex_log_binding(self, *, log_path: str | None, session_id: str | None) -> None:
            calls.append((str(log_path), session_id))

    handle_codex_log_event(
        new_log,
        cwd_extractor=lambda path: str(work_dir),
        session_resolver=lambda cwd: (work_dir / ".ccb" / ".codex-agent1-session", "agent1"),
        session_loader=lambda cwd, instance: _Session(),
        session_id_extractor=lambda path: "new-session",
    )

    assert calls == []


def test_codex_watchdog_allows_initial_binding_within_managed_root(tmp_path: Path) -> None:
    work_dir = tmp_path / "repo"
    work_dir.mkdir(parents=True, exist_ok=True)
    session_root = tmp_path / "managed" / "sessions"
    first_log = session_root / "2026" / "04" / "19" / "rollout-first-session.jsonl"
    first_log.parent.mkdir(parents=True, exist_ok=True)
    first_log.write_text("", encoding="utf-8")

    calls: list[tuple[str, str | None]] = []

    class _Session:
        data = {
            "work_dir": str(work_dir),
            "codex_session_root": str(session_root),
        }
        codex_session_path = ""
        codex_session_id = ""

        def update_codex_log_binding(self, *, log_path: str | None, session_id: str | None) -> None:
            calls.append((str(log_path), session_id))

    handle_codex_log_event(
        first_log,
        cwd_extractor=lambda path: str(work_dir),
        session_resolver=lambda cwd: (work_dir / ".ccb" / ".codex-agent1-session", "agent1"),
        session_loader=lambda cwd, instance: _Session(),
        session_id_extractor=lambda path: "first-session",
    )

    assert calls == [(str(first_log), "first-session")]


def test_codex_inplace_agents_and_external_logs_stay_isolated_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from provider_backends.codex.comm import CodexLogReader
    from provider_backends.codex.comm_runtime.session_content import latest_conversations

    work_dir = tmp_path / "repo"
    session_dir = work_dir / ".ccb"
    work_dir.mkdir(parents=True, exist_ok=True)
    session_dir.mkdir(parents=True, exist_ok=True)

    agent1_root = tmp_path / "agent1-state" / "sessions"
    agent2_root = tmp_path / "agent2-state" / "sessions"
    external_root = tmp_path / "external-codex" / "sessions"
    agent1_log = agent1_root / "2026" / "04" / "19" / "rollout-agent1-session.jsonl"
    agent2_log = agent2_root / "2026" / "04" / "19" / "rollout-agent2-session.jsonl"
    external_log = external_root / "2026" / "04" / "19" / "rollout-external-session.jsonl"
    for path in (agent1_log, agent2_log, external_log):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(
                [
                    json.dumps({"type": "session_meta", "payload": {"cwd": str(work_dir)}}),
                    json.dumps(
                        {
                            "type": "response_item",
                            "payload": {
                                "type": "message",
                                "role": "user",
                                "content": [{"type": "input_text", "text": path.stem}],
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "type": "response_item",
                            "payload": {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": f"reply:{path.stem}"}],
                            },
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    session_file_1 = session_dir / ".codex-agent1-session"
    session_file_2 = session_dir / ".codex-agent2-session"
    session_file_1.write_text(
        json.dumps(
            {
                "work_dir": str(work_dir),
                "codex_home": str(agent1_root.parent),
                "codex_session_root": str(agent1_root),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    session_file_2.write_text(
        json.dumps(
            {
                "work_dir": str(work_dir),
                "codex_home": str(agent2_root.parent),
                "codex_session_root": str(agent2_root),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("CCB_SESSION_FILE", str(session_file_1))
    monkeypatch.setenv("CODEX_SESSION_ROOT", str(agent1_root))

    tracker = CodexBindingTracker(tmp_path / "runtime-agent1")
    assert tracker.refresh_once() is True

    data_1 = json.loads(session_file_1.read_text(encoding="utf-8"))
    assert data_1["codex_session_path"] == str(agent1_log)
    assert str(data_1["codex_session_id"]).endswith("agent1-session")

    reader_1 = CodexLogReader(
        root=agent1_root,
        log_path=Path(data_1["codex_session_path"]),
        session_id_filter=data_1["codex_session_id"],
        work_dir=work_dir,
    )
    assert latest_conversations(reader_1, n=1) == [(agent1_log.stem, f"reply:{agent1_log.stem}")]

    monkeypatch.setenv("CCB_SESSION_FILE", str(session_file_2))
    monkeypatch.setenv("CODEX_SESSION_ROOT", str(agent2_root))

    tracker = CodexBindingTracker(tmp_path / "runtime-agent2")
    assert tracker.refresh_once() is True

    data_2 = json.loads(session_file_2.read_text(encoding="utf-8"))
    assert data_2["codex_session_path"] == str(agent2_log)
    assert str(data_2["codex_session_id"]).endswith("agent2-session")

    reader_2 = CodexLogReader(
        root=agent2_root,
        log_path=Path(data_2["codex_session_path"]),
        session_id_filter=data_2["codex_session_id"],
        work_dir=work_dir,
    )
    assert latest_conversations(reader_2, n=1) == [(agent2_log.stem, f"reply:{agent2_log.stem}")]

    handle_codex_log_event(
        external_log,
        cwd_extractor=lambda path: str(work_dir),
        session_resolver=lambda cwd: (session_file_1, "agent1"),
        session_loader=lambda cwd, instance: CodexProjectSession(session_file=session_file_1, data=json.loads(session_file_1.read_text(encoding="utf-8"))),
        session_id_extractor=lambda path: "external-session",
    )

    rebound_data_1 = json.loads(session_file_1.read_text(encoding="utf-8"))
    assert rebound_data_1["codex_session_path"] == str(agent1_log)
    assert rebound_data_1["codex_session_id"] == data_1["codex_session_id"]
