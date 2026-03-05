from __future__ import annotations

import importlib.util
import json
import sqlite3
from importlib.machinery import SourceFileLoader
from pathlib import Path


def _load_ccb_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "ccb"
    loader = SourceFileLoader("ccb_script_resume", str(script_path))
    spec = importlib.util.spec_from_loader("ccb_script_resume", loader)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _init_minimal_opencode_db(db_path: Path, project_dir: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE session (
                id TEXT PRIMARY KEY,
                directory TEXT,
                time_updated INTEGER
            )
            """
        )
        conn.execute(
            "INSERT INTO session (id, directory, time_updated) VALUES (?, ?, ?)",
            ("ses_test_001", str(project_dir), 1772681205000),
        )
        conn.commit()
    finally:
        conn.close()


def test_opencode_resume_allowed_with_db_history_no_session_dir(tmp_path: Path, monkeypatch) -> None:
    ccb = _load_ccb_module()

    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    storage_root = tmp_path / "opencode" / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    _init_minimal_opencode_db(storage_root.parent / "opencode.db", project_dir)

    monkeypatch.chdir(project_dir)

    import opencode_comm

    monkeypatch.setattr(opencode_comm, "OPENCODE_STORAGE_ROOT", storage_root)
    launcher = ccb.AILauncher(["opencode"], resume=True)

    assert launcher._opencode_resume_allowed() is True


def test_opencode_resume_allowed_from_subdir_with_parent_history(tmp_path: Path, monkeypatch) -> None:
    ccb = _load_ccb_module()

    project_dir = tmp_path / "project"
    sub_dir = project_dir / "sub"
    sub_dir.mkdir(parents=True, exist_ok=True)
    storage_root = tmp_path / "opencode" / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    _init_minimal_opencode_db(storage_root.parent / "opencode.db", project_dir)

    monkeypatch.chdir(sub_dir)

    import opencode_comm

    monkeypatch.setattr(opencode_comm, "OPENCODE_STORAGE_ROOT", storage_root)
    launcher = ccb.AILauncher(["opencode"], resume=True)

    assert launcher._opencode_resume_allowed() is True


def test_opencode_resume_allowed_with_session_diff_history(tmp_path: Path, monkeypatch) -> None:
    ccb = _load_ccb_module()

    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    storage_root = tmp_path / "opencode" / "storage"
    session_diff = storage_root / "session_diff"
    session_diff.mkdir(parents=True, exist_ok=True)
    (session_diff / "ses_abc.json").write_text(
        json.dumps({"id": "ses_abc", "directory": str(project_dir)}, ensure_ascii=True),
        encoding="utf-8",
    )

    monkeypatch.chdir(project_dir)

    import opencode_comm

    monkeypatch.setattr(opencode_comm, "OPENCODE_STORAGE_ROOT", storage_root)
    launcher = ccb.AILauncher(["opencode"], resume=True)

    assert launcher._opencode_resume_allowed() is True
