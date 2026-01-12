from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run(script: str, args: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    exe = sys.executable
    script_path = _repo_root() / "bin" / script
    return subprocess.run(
        [exe, str(script_path), *args],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_cask_daemon_disabled_env(tmp_path: Path) -> None:
    (tmp_path / ".codex-session").write_text("{}", encoding="utf-8")
    env = dict(os.environ)
    env["CCB_CASKD"] = "0"
    env["CCB_CASKD_AUTOSTART"] = "0"
    proc = _run("cask", ["hello"], cwd=tmp_path, env=env)
    assert proc.returncode == 1
    assert "CCB_CASKD=0" in proc.stderr


def test_cask_daemon_required_no_state(tmp_path: Path) -> None:
    (tmp_path / ".codex-session").write_text("{}", encoding="utf-8")
    env = dict(os.environ)
    env["CCB_CASKD"] = "1"
    env["CCB_CASKD_AUTOSTART"] = "0"
    env["CCB_RUN_DIR"] = str(tmp_path / "run")  # isolate from real daemon
    env.pop("CCB_CASKD_STATE_FILE", None)
    proc = _run("cask", ["hello"], cwd=tmp_path, env=env)
    assert proc.returncode == 1
    assert "daemon required" in proc.stderr.lower()


def test_gask_daemon_disabled_env(tmp_path: Path) -> None:
    (tmp_path / ".gemini-session").write_text("{}", encoding="utf-8")
    env = dict(os.environ)
    env["CCB_GASKD"] = "0"
    env["CCB_GASKD_AUTOSTART"] = "0"
    proc = _run("gask", ["hello"], cwd=tmp_path, env=env)
    assert proc.returncode == 1
    assert "CCB_GASKD=0" in proc.stderr


def test_oask_daemon_disabled_env(tmp_path: Path) -> None:
    (tmp_path / ".opencode-session").write_text("{}", encoding="utf-8")
    env = dict(os.environ)
    env["CCB_OASKD"] = "0"
    env["CCB_OASKD_AUTOSTART"] = "0"
    proc = _run("oask", ["hello"], cwd=tmp_path, env=env)
    assert proc.returncode == 1
    assert "CCB_OASKD=0" in proc.stderr

