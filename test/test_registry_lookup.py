from __future__ import annotations

import json
import time
from pathlib import Path

import pane_registry_runtime.api as pane_registry
from pane_registry_runtime.common import REGISTRY_TTL_SECONDS
from project.identity import compute_ccb_project_id
from project.runtime_paths import project_registry_dir


class _FakeBackend:
    def __init__(self, alive: set[str]):
        self._alive = set(alive)

    def is_alive(self, pane_id: str) -> bool:
        return pane_id in self._alive


def _write_registry_file(work_dir: Path, session_id: str, payload: dict) -> Path:
    path = project_registry_dir(work_dir) / f"ccb-session-{session_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_load_registry_by_session_id_ignores_stale_records(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    work_dir = tmp_path / "proj"
    (work_dir / ".ccb").mkdir(parents=True)

    _write_registry_file(
        work_dir,
        "stale",
        {
            "ccb_session_id": "stale",
            "updated_at": int(time.time()) - REGISTRY_TTL_SECONDS - 5,
        },
    )

    monkeypatch.chdir(work_dir)
    assert pane_registry.load_registry_by_session_id("stale") is None


def test_load_registry_by_claude_pane_prefers_newest_fresh_record(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    work_dir = tmp_path / "proj"
    (work_dir / ".ccb").mkdir(parents=True)

    _write_registry_file(
        work_dir,
        "older",
        {
            "ccb_session_id": "older",
            "updated_at": int(time.time()) - 10,
            "providers": {"claude": {"pane_id": "%1"}},
        },
    )
    _write_registry_file(
        work_dir,
        "newer",
        {
            "ccb_session_id": "newer",
            "updated_at": int(time.time()),
            "providers": {"claude": {"pane_id": "%1"}},
        },
    )

    monkeypatch.chdir(work_dir)
    record = pane_registry.load_registry_by_claude_pane("%1")

    assert record is not None
    assert record.get("ccb_session_id") == "newer"


def test_load_registry_by_project_id_persists_inferred_project_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(pane_registry, "get_backend_for_session", lambda _rec: _FakeBackend(alive={"%1"}))

    work_dir = tmp_path / "proj"
    (work_dir / ".ccb").mkdir(parents=True)
    project_id = compute_ccb_project_id(work_dir)
    record_path = _write_registry_file(
        work_dir,
        "legacy",
        {
            "ccb_session_id": "legacy",
            "work_dir": str(work_dir),
            "terminal": "tmux",
            "updated_at": int(time.time()),
            "providers": {"codex": {"pane_id": "%1"}},
        },
    )

    monkeypatch.chdir(work_dir)
    record = pane_registry.load_registry_by_project_id(project_id, "codex")

    assert record is not None
    assert record.get("ccb_project_id") == project_id
    persisted = json.loads(record_path.read_text(encoding="utf-8"))
    assert persisted.get("ccb_project_id") == project_id
