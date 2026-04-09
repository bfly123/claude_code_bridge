from __future__ import annotations

from pathlib import Path

import pytest

from cli import management


def test_find_matching_version_prefers_highest_prefix_match() -> None:
    versions = ["4.0.1", "4.1.0", "4.1.3", "4.2.0", "5.0.0"]
    assert management.find_matching_version("4", versions) == "4.2.0"
    assert management.find_matching_version("4.1", versions) == "4.1.3"
    assert management.find_matching_version("6", versions) is None


def test_latest_version_and_is_newer_version() -> None:
    versions = ["4.1.0", "5.0.0", "4.9.9", "5.2.1"]
    assert management.latest_version(versions) == "5.2.1"
    assert management.is_newer_version("5.2.1", "5.0.0") is True
    assert management.is_newer_version("5.2.1", "5.2.1") is False


def test_format_version_info_handles_missing_fields() -> None:
    assert management.format_version_info({"version": "5.2.8", "commit": "abc1234", "date": "2026-03-22"}) == "v5.2.8 abc1234 2026-03-22"
    assert management.format_version_info({"version": None, "commit": None, "date": None}) == "unknown"


def test_find_install_dir_prefers_explicit_env_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script_root = tmp_path / "script-root"
    script_root.mkdir()
    install_dir = tmp_path / "install-dir"
    install_dir.mkdir()
    (install_dir / "ccb").write_text("", encoding="utf-8")

    monkeypatch.setenv("CODEX_INSTALL_PREFIX", str(install_dir))
    assert management.find_install_dir(script_root) == install_dir


def test_find_install_dir_prefers_script_root_when_installer_present(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script_root = tmp_path / "script-root"
    script_root.mkdir()
    (script_root / "install.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.delenv("CODEX_INSTALL_PREFIX", raising=False)

    assert management.find_install_dir(script_root) == script_root
