from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _git(dir_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['git', *args],
        cwd=dir_path,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_install_sh_stays_lf_under_autocrlf_checkout(tmp_path: Path) -> None:
    repo = tmp_path / 'line-ending-repro'
    repo.mkdir()

    shutil.copy2(REPO_ROOT / '.gitattributes', repo / '.gitattributes')
    shutil.copy2(REPO_ROOT / 'install.sh', repo / 'install.sh')

    _git(repo, 'init')
    _git(repo, 'config', 'user.email', 'test@example.com')
    _git(repo, 'config', 'user.name', 'Test User')
    _git(repo, 'config', 'core.autocrlf', 'true')
    _git(repo, 'add', '.gitattributes', 'install.sh')
    _git(repo, 'commit', '-m', 'init')

    install_path = repo / 'install.sh'
    assert b'\r\n' not in install_path.read_bytes()

    install_path.unlink()
    _git(repo, 'checkout', '--', 'install.sh')

    checked_out = install_path.read_bytes()
    assert checked_out.startswith(b'#!/usr/bin/env bash\n')
    assert b'\r\n' not in checked_out
