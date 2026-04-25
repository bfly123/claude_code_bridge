from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from cli.management_runtime.commands_runtime import version as version_runtime


def test_cmd_version_for_source_install_suggests_git_pull_and_release_update(monkeypatch, tmp_path: Path, capsys) -> None:
    source_dir = tmp_path / "source-install"
    source_dir.mkdir()
    (source_dir / ".git").mkdir()
    monkeypatch.setattr(version_runtime, "find_install_dir", lambda _script_root: source_dir)
    monkeypatch.setattr(
        version_runtime,
        "get_version_info",
        lambda _install_dir: {
            "version": "6.0.12",
            "commit": "abc1234",
            "date": "2026-04-24",
            "install_mode": "source",
            "source_kind": "source",
            "channel": "dev",
        },
    )
    monkeypatch.setattr(
        version_runtime,
        "get_remote_version_info",
        lambda: {"commit": "def5678", "date": "2026-04-25"},
    )

    code = version_runtime.cmd_version(SimpleNamespace(), script_root=tmp_path / "bin-root")

    assert code == 0
    captured = capsys.readouterr()
    assert "Source update available" in captured.out
    assert "git pull" in captured.out
    assert "Run: ccb update" in captured.out


def test_cmd_version_for_release_install_still_suggests_ccb_update(monkeypatch, tmp_path: Path, capsys) -> None:
    install_dir = tmp_path / "release-install"
    install_dir.mkdir()
    monkeypatch.setattr(version_runtime, "find_install_dir", lambda _script_root: install_dir)
    monkeypatch.setattr(
        version_runtime,
        "get_version_info",
        lambda _install_dir: {
            "version": "6.0.11",
            "install_mode": "release",
            "source_kind": "release",
            "channel": "stable",
        },
    )
    monkeypatch.setattr(version_runtime, "get_available_versions", lambda: ["6.0.11", "6.0.12"])

    code = version_runtime.cmd_version(SimpleNamespace(), script_root=tmp_path / "bin-root")

    assert code == 0
    captured = capsys.readouterr()
    assert "Release update available: v6.0.12" in captured.out
    assert "Run: ccb update" in captured.out
