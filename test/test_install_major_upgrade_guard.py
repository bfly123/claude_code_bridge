from __future__ import annotations

import os
import shlex
import subprocess
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO_ROOT / "install.sh"


def _run_major_upgrade_guard(
    *,
    install_prefix: Path,
    build_version: str = "6.0.0",
    confirm: bool = False,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "CCB_LANG": "en",
            "CODEX_INSTALL_PREFIX": str(install_prefix),
            "CCB_BUILD_VERSION": build_version,
        }
    )
    if confirm:
        env["CCB_CONFIRM_MAJOR_UPGRADE"] = "1"
    command = textwrap.dedent(
        f"""
        set -euo pipefail
        source {shlex.quote(str(INSTALL_SH))}
        require_major_upgrade_confirmation
        echo "guard-passed"
        """
    )
    return subprocess.run(
        ["bash", "-lc", command],
        capture_output=True,
        text=True,
        env=env,
    )


def test_major_upgrade_guard_blocks_noninteractive_pre_v6_upgrade(tmp_path: Path) -> None:
    install_prefix = tmp_path / "install"
    install_prefix.mkdir()
    (install_prefix / "VERSION").write_text("5.3.0\n", encoding="utf-8")

    completed = _run_major_upgrade_guard(install_prefix=install_prefix, build_version="6.0.0")

    assert completed.returncode != 0
    assert "Major upgrade confirmation required" in completed.stdout
    assert "CCB_CONFIRM_MAJOR_UPGRADE=1 ccb update" in completed.stdout
    assert "guard-passed" not in completed.stdout


def test_major_upgrade_guard_allows_explicit_confirmation_override(tmp_path: Path) -> None:
    install_prefix = tmp_path / "install"
    install_prefix.mkdir()
    (install_prefix / "VERSION").write_text("5.3.0\n", encoding="utf-8")

    completed = _run_major_upgrade_guard(
        install_prefix=install_prefix,
        build_version="6.0.0",
        confirm=True,
    )

    assert completed.returncode == 0
    assert "guard-passed" in completed.stdout


def test_major_upgrade_guard_does_not_block_non_major_upgrade(tmp_path: Path) -> None:
    install_prefix = tmp_path / "install"
    install_prefix.mkdir()
    (install_prefix / "VERSION").write_text("5.3.0\n", encoding="utf-8")

    completed = _run_major_upgrade_guard(install_prefix=install_prefix, build_version="5.3.1")

    assert completed.returncode == 0
    assert "guard-passed" in completed.stdout
