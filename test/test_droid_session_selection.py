from __future__ import annotations

import json
import os
from pathlib import Path

from provider_backends.droid.comm_runtime.session_selection_runtime import (
    scan_latest_session,
    scan_latest_session_any_project,
)


def _write_session(path: Path, *, cwd: Path, session_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "session_start", "cwd": str(cwd), "id": session_id}) + "\n",
        encoding="utf-8",
    )


class _Reader:
    def __init__(self, root: Path, work_dir: Path, *, scan_limit: int = 5) -> None:
        self.root = root
        self.work_dir = work_dir
        self._scan_limit = scan_limit


def test_scan_latest_session_prefers_matching_work_dir(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    work_dir = tmp_path / "repo"
    other_dir = tmp_path / "other"
    work_dir.mkdir()
    other_dir.mkdir()

    older = root / "2026" / "older.jsonl"
    newer = root / "2026" / "newer.jsonl"
    _write_session(older, cwd=work_dir, session_id="sid-old")
    _write_session(newer, cwd=other_dir, session_id="sid-new")
    older_stat = older.stat()
    newer_stat = newer.stat()
    os.utime(older, (older_stat.st_atime + 20, older_stat.st_mtime + 20))
    os.utime(newer, (newer_stat.st_atime + 30, newer_stat.st_mtime + 30))

    assert scan_latest_session(_Reader(root, work_dir)) == older


def test_scan_latest_session_any_project_returns_latest_log(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    work_dir = tmp_path / "repo"
    work_dir.mkdir()

    older = root / "2026" / "older.jsonl"
    newer = root / "2026" / "newer.jsonl"
    _write_session(older, cwd=work_dir, session_id="sid-old")
    _write_session(newer, cwd=work_dir, session_id="sid-new")
    newer_stat = newer.stat()
    os.utime(newer, (newer_stat.st_atime + 30, newer_stat.st_mtime + 30))

    assert scan_latest_session_any_project(_Reader(root, work_dir)) == newer
