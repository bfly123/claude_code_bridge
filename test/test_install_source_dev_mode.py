from __future__ import annotations

import os
import shlex
import subprocess
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO_ROOT / "install.sh"


def _run_source_dev_snippet(tmp_path: Path, shell_body: str) -> subprocess.CompletedProcess[str]:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home_dir),
            "CODEX_INSTALL_PREFIX": str(tmp_path / "managed"),
            "CODEX_BIN_DIR": str(tmp_path / "bin"),
            "CODEX_HOME": str(tmp_path / "codex-home"),
            "CCB_LANG": "en",
            "CCB_SOURCE_KIND": "source",
            "CCB_SOURCE_ROOT": str(REPO_ROOT),
        }
    )
    command = textwrap.dedent(
        f"""
        set -euo pipefail
        source {shlex.quote(str(INSTALL_SH))}
        {shell_body}
        """
    )
    return subprocess.run(
        ["bash", "-lc", command],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
    )


def test_source_dev_install_links_live_bin_and_codex_skill_assets(tmp_path: Path) -> None:
    completed = _run_source_dev_snippet(
        tmp_path,
        """
        install_bin_links
        install_codex_skills
        """,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout

    bin_dir = tmp_path / "bin"
    ccb_path = bin_dir / "ccb"
    assert ccb_path.exists()
    if ccb_path.is_symlink():
        assert ccb_path.resolve() == REPO_ROOT / "ccb"
    else:
        assert str(REPO_ROOT / "ccb") in ccb_path.read_text(encoding="utf-8")

    ask_skill_md = tmp_path / "codex-home" / "skills" / "ask" / "SKILL.md"
    assert ask_skill_md.is_symlink()
    assert ask_skill_md.resolve() == REPO_ROOT / "codex_skills" / "ask" / "SKILL.md"

    readme_path = tmp_path / "codex-home" / "skills" / "all-plan" / "README.md"
    assert readme_path.is_symlink()
    assert readme_path.resolve() == REPO_ROOT / "codex_skills" / "all-plan" / "README.md"

    references_path = tmp_path / "codex-home" / "skills" / "all-plan" / "references"
    assert references_path.is_symlink()
    assert references_path.resolve() == REPO_ROOT / "codex_skills" / "all-plan" / "references"
