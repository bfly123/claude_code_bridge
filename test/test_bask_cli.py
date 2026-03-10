from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_ask(args: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    exe = sys.executable
    script_path = _repo_root() / "bin" / "ask"
    return subprocess.run(
        [exe, str(script_path), *args],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _run_bask(args: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    exe = sys.executable
    script_path = _repo_root() / "bin" / "bask"
    return subprocess.run(
        [exe, str(script_path), *args],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_ask_recognizes_codebuddy_provider(tmp_path: Path) -> None:
    """ask codebuddy should be accepted as a valid provider."""
    env = dict(os.environ)
    env["CCB_CALLER"] = "claude"
    env["CCB_UNIFIED_ASKD"] = "1"
    env["CCB_ASKD_AUTOSTART"] = "0"
    env["CCB_RUN_DIR"] = str(tmp_path / "run")

    proc = _run_ask(["codebuddy", "hello"], cwd=tmp_path, env=env)

    # Should fail because daemon is not running, but NOT because of unknown provider
    assert "Unknown provider" not in proc.stderr
    assert proc.returncode != 0  # Expected: daemon not available


def test_ask_rejects_unknown_provider(tmp_path: Path) -> None:
    """ask with invalid provider should be rejected."""
    env = dict(os.environ)
    env["CCB_CALLER"] = "claude"

    proc = _run_ask(["notaprovider", "hello"], cwd=tmp_path, env=env)

    assert "Unknown provider" in proc.stderr
    assert proc.returncode != 0


def test_bask_no_session_shows_error(tmp_path: Path) -> None:
    """bask should report error when no codebuddy session exists."""
    env = dict(os.environ)
    env["CCB_BASKD"] = "1"
    env["CCB_BASKD_AUTOSTART"] = "0"
    env["CCB_RUN_DIR"] = str(tmp_path / "run")
    # Remove any session file env
    env.pop("CCB_SESSION_FILE", None)

    proc = _run_bask(["hello"], cwd=tmp_path, env=env)

    assert proc.returncode != 0
    # Should mention CodeBuddy session not found
    assert "CodeBuddy" in proc.stderr or "codebuddy" in proc.stderr.lower() or "session" in proc.stderr.lower()


def test_bask_help_flag(tmp_path: Path) -> None:
    """bask --help should show usage without error."""
    env = dict(os.environ)
    proc = _run_bask(["--help"], cwd=tmp_path, env=env)

    assert proc.returncode == 0
    assert "bask" in proc.stderr.lower() or "bask" in proc.stdout.lower() or "usage" in proc.stderr.lower()


def test_bask_empty_message_shows_error(tmp_path: Path) -> None:
    """bask with empty message should show error."""
    env = dict(os.environ)
    proc = _run_bask([], cwd=tmp_path, env=env)

    assert proc.returncode != 0
