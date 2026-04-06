from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from provider_backends.claude.registry_runtime.events import (
    handle_new_log_file,
    handle_new_log_file_global,
    handle_sessions_index,
)
from provider_backends.claude.registry_runtime.state import SessionEntry, WatcherEntry


class _DummyLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, *, session_id: str = "", session_path: str = ""):
        self.claude_session_id = session_id
        self.claude_session_path = session_path
        self.updated: list[tuple[str, str]] = []

    def update_claude_binding(self, *, session_path: Path, session_id: str) -> None:
        self.claude_session_path = str(session_path)
        self.claude_session_id = session_id
        self.updated.append((str(session_path), session_id))


def _registry(tmp_path: Path):
    return SimpleNamespace(
        _lock=_DummyLock(),
        _sessions={},
        _watchers={},
        _pending_logs={},
        _log_last_check={},
        _claude_root=tmp_path / "claude-root",
        _find_claude_session_file=lambda work_dir: tmp_path / ".ccb" / ".claude-session",
        _load_claude_session=lambda work_dir: None,
    )


def test_handle_new_log_file_global_updates_session_and_session_file(tmp_path: Path, monkeypatch) -> None:
    from provider_backends.claude.registry_runtime.events_runtime import global_logs

    registry = _registry(tmp_path)
    work_dir = tmp_path / "repo"
    session = _FakeSession()
    registry._sessions[str(work_dir)] = SessionEntry(work_dir=work_dir, session=session, valid=True)
    log_path = tmp_path / "claude-log.jsonl"
    log_path.write_text("", encoding="utf-8")

    captured_updates: list[tuple[Path, Path, str]] = []
    monkeypatch.setattr(global_logs, "read_log_meta_with_retry", lambda path: (str(work_dir), "sid-1", False))
    monkeypatch.setattr(
        global_logs,
        "update_session_file",
        lambda registry_obj, current_work_dir, *, session_path, session_id: captured_updates.append(
            (current_work_dir, session_path, session_id)
        ),
    )

    handle_new_log_file_global(registry, log_path)

    assert captured_updates == [(work_dir, log_path, "sid-1")]
    assert session.updated == [(str(log_path), "sid-1")]


def test_handle_new_log_file_marks_pending_when_unscoped_log_does_not_update(tmp_path: Path, monkeypatch) -> None:
    from provider_backends.claude.registry_runtime.events_runtime import project_logs

    registry = _registry(tmp_path)
    work_dir = tmp_path / "repo"
    session = _FakeSession(session_id="sid-existing", session_path=str(tmp_path / "current.jsonl"))
    registry._sessions["repo"] = SessionEntry(work_dir=work_dir, session=session, valid=True)
    registry._watchers["project-a"] = WatcherEntry(watcher=SimpleNamespace(), keys={"repo"})
    log_path = tmp_path / "other.jsonl"
    log_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(project_logs, "read_log_meta_with_retry", lambda path: (None, "sid-existing", False))
    monkeypatch.setattr(project_logs, "should_overwrite_binding", lambda current_path, candidate_path: False)

    handle_new_log_file(registry, "project-a", log_path)

    assert registry._pending_logs[str(log_path)] > 0
    assert session.updated == []


def test_handle_sessions_index_updates_matching_registry_entries(tmp_path: Path, monkeypatch) -> None:
    from provider_backends.claude.registry_runtime.events_runtime import sessions_index

    registry = _registry(tmp_path)
    work_dir = tmp_path / "repo"
    session = _FakeSession()
    registry._sessions["repo"] = SessionEntry(work_dir=work_dir, session=session, valid=True)
    registry._watchers["project-a"] = WatcherEntry(watcher=SimpleNamespace(), keys={"repo"})

    index_path = tmp_path / "sessions-index.json"
    index_path.write_text("{}", encoding="utf-8")
    bound_log = tmp_path / "bound-session.jsonl"
    bound_log.write_text("", encoding="utf-8")

    captured_updates: list[tuple[Path, Path, str]] = []
    monkeypatch.setattr(sessions_index, "parse_sessions_index", lambda wd, root: bound_log)
    monkeypatch.setattr(
        sessions_index,
        "update_session_file",
        lambda registry_obj, current_work_dir, *, session_path, session_id: captured_updates.append(
            (current_work_dir, session_path, session_id)
        ),
    )

    handle_sessions_index(registry, "project-a", index_path)

    assert captured_updates == [(work_dir, bound_log, "bound-session")]
    assert session.updated == [(str(bound_log), "bound-session")]
