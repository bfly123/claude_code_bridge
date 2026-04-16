from __future__ import annotations

from pathlib import Path
import subprocess

import pytest


def _is_ephemeral_repo_artifact(path_text: str) -> bool:
    path = Path(path_text.strip())
    if not path.parts:
        return False
    first = path.parts[0]
    return first == ".tmp_pytest" or first.startswith(".tmp_test_env_")


def test_git_index_does_not_track_ephemeral_test_artifacts() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    if not (repo_root / ".git").exists():
        pytest.skip("git checkout required")

    completed = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = [
        line
        for line in completed.stdout.splitlines()
        if line.strip() and _is_ephemeral_repo_artifact(line)
    ]

    assert tracked == []
