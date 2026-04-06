from __future__ import annotations

from pathlib import Path

from opencode_runtime.paths_runtime.project_id import compute_opencode_project_id
from opencode_runtime.paths_runtime.roots_runtime.service import first_existing_path


def test_compute_opencode_project_id_prefers_cached_git_value(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    git_dir = project_root / '.git'
    git_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / 'opencode').write_text('cached-project-id\n', encoding='utf-8')

    assert compute_opencode_project_id(project_root) == 'cached-project-id'


def test_first_existing_path_returns_first_real_candidate(tmp_path: Path) -> None:
    missing = tmp_path / 'missing'
    existing = tmp_path / 'exists'
    existing.mkdir()

    assert first_existing_path([missing, existing]) == existing

