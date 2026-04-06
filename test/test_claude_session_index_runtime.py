from __future__ import annotations

import json

from provider_backends.claude.session_index_runtime import (
    load_index_entries,
    resolve_registry_index_location,
    select_best_session_path,
)
from provider_backends.claude.registry_support.pathing import project_key_for_path


def test_resolve_registry_index_location_falls_back_to_resolved_workdir(tmp_path) -> None:
    real_work_dir = tmp_path / "repo"
    real_work_dir.mkdir()
    linked_work_dir = tmp_path / "repo-link"
    linked_work_dir.symlink_to(real_work_dir)

    resolved_key_dir = tmp_path / "claude-root" / project_key_for_path(real_work_dir.resolve())
    resolved_key_dir.mkdir(parents=True)
    (resolved_key_dir / "sessions-index.json").write_text('{"entries": []}', encoding="utf-8")

    location = resolve_registry_index_location(linked_work_dir, root=tmp_path / "claude-root")

    assert location is not None
    assert location.project_dir == resolved_key_dir


def test_select_best_session_path_prefers_newest_matching_entry(tmp_path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    older = project_dir / "older.jsonl"
    newer = project_dir / "newer.jsonl"
    older.write_text("", encoding="utf-8")
    newer.write_text("", encoding="utf-8")

    entries = load_index_entries(
        _write_index(
            tmp_path / "sessions-index.json",
            [
                {"projectPath": "/repo", "fullPath": "older.jsonl", "fileMtime": 10},
                {"projectPath": "/repo", "fullPath": "newer.jsonl", "fileMtime": 20},
                {"projectPath": "/other", "fullPath": "ignored.jsonl", "fileMtime": 30},
            ],
        )
    )

    best = select_best_session_path(
        entries or [],
        candidates={"/repo"},
        project_dir=project_dir,
    )

    assert best == newer


def _write_index(path, entries):
    path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    return path
