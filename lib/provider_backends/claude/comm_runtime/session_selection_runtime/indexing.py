from __future__ import annotations

from pathlib import Path

from ...session_index_runtime import candidate_paths_for_work_dir, load_index_entries, project_index_location, select_best_session_path

from .membership import project_dir, session_belongs_to_current_project


def parse_sessions_index(reader) -> Path | None:
    if not reader._use_sessions_index:
        return None
    location = project_index_location(root=Path(), project_dir=project_dir(reader))
    if location is None:
        return None
    entries = load_index_entries(location.index_path)
    if entries is None:
        return None
    return select_best_session_path(
        entries,
        candidates=candidate_paths_for_work_dir(reader.work_dir, include_env_pwd=False),
        project_dir=location.project_dir,
        session_filter=lambda session_path: session_belongs_to_current_project(reader, session_path),
    )


__all__ = ["parse_sessions_index"]
