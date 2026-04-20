from __future__ import annotations

from pathlib import Path

from provider_backends.claude.session_index_runtime import (
    candidate_paths_for_work_dir,
    load_index_entries,
    resolve_registry_index_location,
    select_best_session_path,
)


def parse_sessions_index(work_dir: Path, *, root: Path) -> Path | None:
    candidates = candidate_paths_for_work_dir(work_dir, include_env_pwd=False)
    location = resolve_registry_index_location(work_dir, root=root)
    if location is None:
        return None
    entries = load_index_entries(location.index_path)
    if entries is None:
        return None
    return select_best_session_path(
        entries,
        candidates=candidates,
        project_dir=location.project_dir,
    )


__all__ = ["parse_sessions_index"]
