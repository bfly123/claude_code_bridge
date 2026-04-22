from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

repo_root = Path(__file__).resolve().parents[1]
lib_dir = repo_root / "lib"
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

import project.resolver as project_resolver_module


def pytest_configure() -> None:
    if str(lib_dir) not in sys.path:
        sys.path.insert(0, str(lib_dir))


def _write_provider_stub_launchers(bin_dir: Path) -> None:
    stub_path = (repo_root / "test" / "stubs" / "provider_stub.py").resolve()
    python_exe = sys.executable
    providers = ("codex", "gemini", "claude", "opencode", "droid")
    for provider in providers:
        posix_launcher = bin_dir / provider
        posix_launcher.write_text(
            "\n".join(
                [
                    "#!/bin/sh",
                    f'exec "{python_exe}" "{stub_path}" --provider {provider} "$@"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        posix_launcher.chmod(posix_launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        windows_launcher = bin_dir / f"{provider}.cmd"
        windows_launcher.write_text(
            f'@"{python_exe}" "{stub_path}" --provider {provider} %*\r\n',
            encoding="utf-8",
        )


@pytest.fixture(autouse=True)
def _ignore_host_level_tmp_anchor(monkeypatch, tmp_path_factory) -> None:
    original = project_resolver_module.find_parent_project_anchor_dir
    pytest_tmp_root = tmp_path_factory.getbasetemp().resolve()

    def _patched(path: Path):
        result = original(path)
        if result is None:
            return None
        anchor_root = result.parent.resolve()
        if pytest_tmp_root.is_relative_to(anchor_root) and not anchor_root.is_relative_to(pytest_tmp_root):
            return None
        return result

    monkeypatch.setattr(project_resolver_module, 'find_parent_project_anchor_dir', _patched)


@pytest.fixture(autouse=True)
def _install_provider_stubs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / ".home"
    bin_dir = tmp_path / ".stub-bin"
    home_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    _write_provider_stub_launchers(bin_dir)

    path_entries = [str(bin_dir)]
    existing_path = os.environ.get("PATH")
    if existing_path:
        path_entries.append(existing_path)

    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))
    monkeypatch.setenv("PATH", os.pathsep.join(path_entries))
    monkeypatch.setenv("STUB_DELAY", "1.5")
    monkeypatch.setenv("CCB_REPLY_LANG", "en")
    monkeypatch.setenv("CCB_CLAUDE_SKILLS", "0")
