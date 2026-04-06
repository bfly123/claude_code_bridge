from __future__ import annotations

import json
import os
from pathlib import Path

from provider_backends.opencode.runtime.reader_support import (
    build_work_dir_candidates,
    detect_project_id_for_workdir,
)


def test_build_work_dir_candidates_deduplicates_normalized_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    work_dir = tmp_path / "repo"
    work_dir.mkdir()
    monkeypatch.setenv("PWD", str(work_dir))

    candidates = build_work_dir_candidates(work_dir)

    assert candidates == [str(work_dir)]


def test_detect_project_id_for_workdir_prefers_best_matching_project_file(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "storage"
    projects_dir = storage_root / "project"
    projects_dir.mkdir(parents=True)
    work_dir = tmp_path / "repo"
    work_dir.mkdir()
    older = projects_dir / "older.json"
    newer = projects_dir / "newer.json"
    older.write_text(
        json.dumps({"id": "proj-old", "worktree": str(work_dir), "time": {"updated": 1}}),
        encoding="utf-8",
    )
    newer.write_text(
        json.dumps({"id": "proj-new", "worktree": str(work_dir), "time": {"updated": 2}}),
        encoding="utf-8",
    )
    os.utime(newer, (newer.stat().st_atime, newer.stat().st_mtime + 10))

    project_id = detect_project_id_for_workdir(
        storage_root=storage_root,
        work_dir=work_dir,
        load_json_fn=lambda path: json.loads(path.read_text(encoding="utf-8")),
        allow_parent_match=False,
    )

    assert project_id == "proj-new"
