"""Tests for CCB_PROJECT_DIR env var support in project discovery."""
from __future__ import annotations

from pathlib import Path

import pytest

from project.discovery import (
    CCB_PROJECT_DIR_ENV,
    find_nearest_project_anchor,
)


def _make_ccb_dir(parent: Path) -> Path:
    (parent / '.ccb').mkdir(parents=True, exist_ok=True)
    return parent


class TestCcbProjectDirEnv:
    def test_env_unset_walks_cwd(self, monkeypatch, tmp_path):
        monkeypatch.delenv(CCB_PROJECT_DIR_ENV, raising=False)
        _make_ccb_dir(tmp_path)
        nested = tmp_path / 'nested' / 'deeper'
        nested.mkdir(parents=True)
        assert find_nearest_project_anchor(nested) == tmp_path.resolve()

    def test_env_set_with_valid_ccb_dir_wins_over_cwd(self, monkeypatch, tmp_path):
        env_project = _make_ccb_dir(tmp_path / 'env_project')
        cwd_project = _make_ccb_dir(tmp_path / 'cwd_project')
        monkeypatch.setenv(CCB_PROJECT_DIR_ENV, str(env_project))
        assert find_nearest_project_anchor(cwd_project) == env_project.resolve()

    def test_env_set_with_path_that_has_no_ccb_dir_falls_through(self, monkeypatch, tmp_path):
        env_path = tmp_path / 'empty_dir'
        env_path.mkdir()
        cwd_project = _make_ccb_dir(tmp_path / 'cwd_project')
        monkeypatch.setenv(CCB_PROJECT_DIR_ENV, str(env_path))
        assert find_nearest_project_anchor(cwd_project) == cwd_project.resolve()

    def test_env_set_with_nonexistent_path_falls_through(self, monkeypatch, tmp_path):
        cwd_project = _make_ccb_dir(tmp_path / 'cwd_project')
        monkeypatch.setenv(CCB_PROJECT_DIR_ENV, str(tmp_path / 'does_not_exist'))
        assert find_nearest_project_anchor(cwd_project) == cwd_project.resolve()

    def test_env_set_to_empty_string_treated_as_unset(self, monkeypatch, tmp_path):
        cwd_project = _make_ccb_dir(tmp_path / 'cwd_project')
        monkeypatch.setenv(CCB_PROJECT_DIR_ENV, '')
        assert find_nearest_project_anchor(cwd_project) == cwd_project.resolve()

    def test_env_bypasses_dangerous_root_check(self, monkeypatch, tmp_path):
        """User explicit intent via env overrides the $HOME-like dangerous check."""
        env_project = _make_ccb_dir(tmp_path)
        monkeypatch.setenv(CCB_PROJECT_DIR_ENV, str(env_project))
        unrelated = tmp_path.parent
        assert find_nearest_project_anchor(unrelated) == env_project.resolve()
