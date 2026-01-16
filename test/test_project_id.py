from __future__ import annotations

import os
from pathlib import Path

import pytest

from project_id import compute_ccb_project_id, normalize_work_dir


def test_normalize_work_dir_basic() -> None:
    assert normalize_work_dir("/a/b/../c") == "/a/c"
    assert normalize_work_dir("/a//b///c") == "/a/b/c"


def test_normalize_work_dir_wsl_drive_mapping() -> None:
    assert normalize_work_dir("/mnt/C/Users/alice") == "c:/Users/alice"
    assert normalize_work_dir("/mnt/c/Users/alice") == "c:/Users/alice"


def test_compute_ccb_project_id_stable_for_same_dir(tmp_path: Path) -> None:
    pid1 = compute_ccb_project_id(tmp_path)
    pid2 = compute_ccb_project_id(tmp_path)
    assert pid1
    assert pid1 == pid2


def test_compute_ccb_project_id_different_for_subdirs(tmp_path: Path) -> None:
    """
    Since we no longer search upward for .ccb_config anchors,
    subdirectories have different project_ids than their parents.
    This is acceptable because cask/gask/oask are always invoked from the project root.
    """
    (tmp_path / ".ccb_config").mkdir(parents=True, exist_ok=True)
    subdir = tmp_path / "a" / "b"
    subdir.mkdir(parents=True, exist_ok=True)

    pid_root = compute_ccb_project_id(tmp_path)
    pid_sub = compute_ccb_project_id(subdir)
    assert pid_root
    assert pid_sub
    assert pid_root != pid_sub  # Different directories = different project_ids


def test_compute_ccb_project_id_respects_env_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "root"
    child = root / "sub"
    child.mkdir(parents=True, exist_ok=True)

    # No anchor: env var should still force a stable root id.
    monkeypatch.setenv("CCB_PROJECT_ROOT", str(root))
    pid_root = compute_ccb_project_id(root)
    pid_child = compute_ccb_project_id(child)
    assert pid_root
    assert pid_root == pid_child

    # Invalid env root should not crash.
    monkeypatch.setenv("CCB_PROJECT_ROOT", str(tmp_path / "does-not-exist"))
    assert compute_ccb_project_id(child)
