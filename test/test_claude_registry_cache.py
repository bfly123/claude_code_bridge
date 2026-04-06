from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json

from provider_backends.claude.registry import ClaudeSessionRegistry
from provider_backends.claude.registry_runtime.cache import get_session, invalidate, load_and_cache, register_session, remove
from provider_backends.claude.registry_runtime.state import SessionEntry


class _DummyLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, *, session_file: Path | None = None, ensure_ok: bool = True):
        self.session_file = session_file
        self._ensure_ok = ensure_ok

    def ensure_pane(self):
        return self._ensure_ok, 'ok'


def _registry():
    return SimpleNamespace(_lock=_DummyLock(), _sessions={})


def test_get_session_reloads_when_session_file_mtime_changes(tmp_path: Path) -> None:
    registry = _registry()
    work_dir = tmp_path / 'repo'
    work_dir.mkdir()
    session_file = tmp_path / '.claude-session'
    session_file.write_text('{}', encoding='utf-8')
    registry._sessions[str(work_dir)] = SessionEntry(
        work_dir=work_dir,
        session='cached-session',
        session_file=session_file,
        file_mtime=0.0,
        valid=True,
    )
    logs: list[str] = []

    reloaded = get_session(
        registry,
        work_dir,
        find_session_file_fn=lambda work_dir: session_file,
        write_log_fn=logs.append,
        load_and_cache_fn=lambda work_dir: SimpleNamespace(session='reloaded-session'),
    )

    assert reloaded == 'reloaded-session'
    assert logs == [f'[INFO] Session file changed, reloading: {work_dir}']


def test_register_session_stores_valid_entry_and_ensures_watchers(tmp_path: Path) -> None:
    registry = _registry()
    work_dir = tmp_path / 'repo'
    work_dir.mkdir()
    session_file = tmp_path / '.claude-session'
    session_file.write_text('{}', encoding='utf-8')
    session = _FakeSession(session_file=session_file)
    watcher_calls: list[tuple[Path, str]] = []

    register_session(
        registry,
        work_dir,
        session,
        session_entry_cls=SessionEntry,
        ensure_watchers_for_work_dir_fn=lambda work_dir, key: watcher_calls.append((work_dir, key)),
    )

    entry = registry._sessions[str(work_dir)]
    assert entry.valid is True
    assert entry.session is session
    assert watcher_calls == [(work_dir, str(work_dir))]


def test_load_and_cache_returns_none_for_unhealthy_session_but_caches_entry(tmp_path: Path) -> None:
    registry = _registry()
    work_dir = tmp_path / 'repo'
    work_dir.mkdir()
    session_file = tmp_path / '.claude-session'
    session_file.write_text('{}', encoding='utf-8')

    result = load_and_cache(
        registry,
        work_dir,
        session_entry_cls=SessionEntry,
        load_session_fn=lambda work_dir: _FakeSession(session_file=session_file, ensure_ok=False),
        find_session_file_fn=lambda work_dir: session_file,
    )

    assert result is None
    assert registry._sessions[str(work_dir)].valid is False
    assert registry._sessions[str(work_dir)].session_file == session_file


def test_invalidate_and_remove_release_watchers(tmp_path: Path) -> None:
    registry = _registry()
    work_dir = tmp_path / 'repo'
    entry = SessionEntry(work_dir=work_dir, session='sess', valid=True)
    registry._sessions[str(work_dir)] = entry
    released: list[tuple[Path, str]] = []
    logs: list[str] = []

    invalidate(
        registry,
        work_dir,
        write_log_fn=logs.append,
        release_watchers_for_work_dir_fn=lambda work_dir, key: released.append((work_dir, key)),
    )
    remove(
        registry,
        work_dir,
        write_log_fn=logs.append,
        release_watchers_for_work_dir_fn=lambda work_dir, key: released.append((work_dir, key)),
    )

    assert logs == [
        f'[INFO] Session invalidated: {work_dir}',
        f'[INFO] Session removed: {work_dir}',
    ]
    assert released == [
        (work_dir, str(work_dir)),
        (work_dir, str(work_dir)),
    ]
    assert str(work_dir) not in registry._sessions


def test_registry_resolves_named_workspace_session_file(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    workspace = tmp_path / "workspace-agent3"
    workspace.mkdir()
    (workspace / ".ccb-workspace.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "record_type": "workspace_binding",
                "target_project": str(project_root),
                "project_id": "demo-project",
                "agent_name": "agent3",
                "workspace_mode": "linked",
                "workspace_path": str(workspace),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    session_file = project_root / ".ccb" / ".claude-agent3-session"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(
        json.dumps(
            {
                "active": True,
                "work_dir": str(workspace),
                "claude_session_id": "sid",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    registry = ClaudeSessionRegistry()

    assert registry._find_claude_session_file(workspace) == session_file
    loaded = registry._load_claude_session(workspace)
    assert loaded is not None
    assert loaded.session_file == session_file
