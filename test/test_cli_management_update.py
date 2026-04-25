from __future__ import annotations

import tarfile
from pathlib import Path
from types import SimpleNamespace

from cli.management_runtime.commands_runtime import update as update_runtime


def test_cmd_update_defaults_to_latest_release(monkeypatch, tmp_path: Path) -> None:
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    tmp_base = tmp_path / "tmp-base"
    tmp_base.mkdir()
    captured: dict[str, object] = {}

    monkeypatch.setenv("CODEX_INSTALL_PREFIX", str(install_dir))
    monkeypatch.setattr(update_runtime.platform, "system", lambda: "Linux")
    monkeypatch.setattr(update_runtime, "pick_temp_base_dir", lambda _install_dir: tmp_base)
    monkeypatch.setattr(update_runtime, "get_available_versions", lambda: ["5.1.0", "5.3.0", "5.2.8"])

    def _fake_update_via_tarball(tmp_base_arg, *, install_dir, target_version, old_info):
        captured["tmp_base"] = tmp_base_arg
        captured["install_dir"] = install_dir
        captured["target_version"] = target_version
        captured["old_info"] = old_info
        return 0

    monkeypatch.setattr(update_runtime, "_update_via_tarball", _fake_update_via_tarball)

    code = update_runtime.cmd_update(SimpleNamespace(target=None), script_root=tmp_path / "script-root")

    assert code == 0
    assert captured["tmp_base"] == tmp_base
    assert captured["install_dir"] == install_dir
    assert captured["target_version"] == "5.3.0"


def test_cmd_update_errors_when_latest_release_cannot_be_resolved(monkeypatch, tmp_path: Path) -> None:
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    tmp_base = tmp_path / "tmp-base"
    tmp_base.mkdir()

    monkeypatch.setenv("CODEX_INSTALL_PREFIX", str(install_dir))
    monkeypatch.setattr(update_runtime.platform, "system", lambda: "Linux")
    monkeypatch.setattr(update_runtime, "pick_temp_base_dir", lambda _install_dir: tmp_base)
    monkeypatch.setattr(update_runtime, "get_available_versions", lambda: [])

    code = update_runtime.cmd_update(SimpleNamespace(target=None), script_root=tmp_path / "script-root")

    assert code == 1


def test_cmd_update_rejects_non_unix_platform(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(update_runtime.platform, "system", lambda: "Windows")

    code = update_runtime.cmd_update(SimpleNamespace(target=None), script_root=tmp_path / "script-root")

    assert code == 1
    captured = capsys.readouterr()
    assert "Linux, macOS, or WSL" in captured.out


def test_cmd_update_allows_source_dev_install_and_targets_managed_prefix(monkeypatch, tmp_path: Path, capsys) -> None:
    source_dir = tmp_path / "source-install"
    source_dir.mkdir()
    (source_dir / "install.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (source_dir / ".git").mkdir()
    managed_prefix = tmp_path / "managed-install"
    monkeypatch.setattr(update_runtime.platform, "system", lambda: "Linux")
    monkeypatch.setenv("CODEX_INSTALL_PREFIX", str(managed_prefix))
    monkeypatch.setattr(update_runtime, "pick_temp_base_dir", lambda _install_dir: tmp_path / "tmp-base")
    monkeypatch.setattr(update_runtime, "_resolve_latest_release_version", lambda: "6.0.12")
    calls: dict[str, object] = {}

    def _fake_update_via_tarball(tmp_base_arg, *, install_dir, target_version, old_info):
        calls["tmp_base"] = tmp_base_arg
        calls["install_dir"] = install_dir
        calls["target_version"] = target_version
        calls["old_info"] = old_info
        return 0

    monkeypatch.setattr(update_runtime, "_update_via_tarball", _fake_update_via_tarball)
    monkeypatch.setattr(
        update_runtime,
        "get_version_info",
        lambda install_dir: {
            "install_mode": "source" if install_dir == source_dir else "release",
            "source_kind": "source" if install_dir == source_dir else "release",
            "version": "6.0.11",
        },
    )

    code = update_runtime.cmd_update(SimpleNamespace(target=None), script_root=source_dir)

    assert code == 0
    captured = capsys.readouterr()
    assert "source/dev checkout" in captured.out
    assert "Global `ccb` links now target the release install" in captured.out
    assert calls["install_dir"] == managed_prefix
    assert calls["target_version"] == "6.0.12"
    assert calls["old_info"]["install_mode"] == "source"


def test_release_artifact_name_uses_linux_arch_aliases(monkeypatch) -> None:
    monkeypatch.setattr(update_runtime.platform, "system", lambda: "Linux")
    monkeypatch.setattr(update_runtime.platform, "machine", lambda: "amd64")
    assert update_runtime._release_artifact_name() == "ccb-linux-x86_64.tar.gz"

    monkeypatch.setattr(update_runtime.platform, "machine", lambda: "arm64")
    assert update_runtime._release_artifact_name() == "ccb-linux-aarch64.tar.gz"


def test_release_artifact_name_uses_macos_universal_bundle(monkeypatch) -> None:
    monkeypatch.setattr(update_runtime.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(update_runtime.platform, "machine", lambda: "arm64")

    assert update_runtime._release_artifact_name() == "ccb-macos-universal.tar.gz"


def test_release_artifact_url_points_to_release_download() -> None:
    url = update_runtime._release_artifact_url("6.0.0", artifact_name="ccb-linux-x86_64.tar.gz")

    assert url == "https://github.com/bfly123/claude_code_bridge/releases/download/v6.0.0/ccb-linux-x86_64.tar.gz"


def test_release_extract_dir_name_strips_tar_suffixes() -> None:
    assert update_runtime._release_extract_dir_name("ccb-linux-x86_64.tar.gz") == "ccb-linux-x86_64"
    assert update_runtime._release_extract_dir_name("ccb-linux-aarch64.tgz") == "ccb-linux-aarch64"
    assert update_runtime._release_extract_dir_name("ccb-preview.zip") == "ccb-preview"


def test_update_via_tarball_uses_staged_unix_installer(monkeypatch, tmp_path: Path) -> None:
    tmp_base = tmp_path / "tmp-base"
    tmp_base.mkdir()
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    calls: dict[str, object] = {}
    monkeypatch.setattr(update_runtime.platform, "system", lambda: "Linux")
    monkeypatch.setattr(update_runtime.platform, "machine", lambda: "x86_64")

    def _fake_download(_url: str, destination: Path) -> bool:
        extracted_dir = tmp_base / "payload-src"
        extracted_dir.mkdir(parents=True, exist_ok=True)
        (extracted_dir / "install.sh").write_text("#!/usr/bin/env bash\r\nexit 0\r\n", encoding="utf-8")
        with tarfile.open(destination, "w:gz") as archive:
            archive.add(extracted_dir, arcname="ccb-linux-x86_64")
        return True

    monkeypatch.setattr(update_runtime, "download_tarball", _fake_download)
    monkeypatch.setattr(update_runtime, "get_version_info", lambda _install_dir: {"version": "6.0.8"})
    monkeypatch.setattr(update_runtime, "_print_update_outcome", lambda old_info, new_info: None)

    def _fake_run_staged(action: str, *, source_dir: Path, install_dir: Path, extra_env: dict[str, str] | None = None) -> int:
        calls["action"] = action
        calls["source_dir"] = source_dir
        calls["install_dir"] = install_dir
        calls["extra_env"] = dict(extra_env or {})
        return 0

    monkeypatch.setattr(update_runtime, "run_staged_unix_installer", _fake_run_staged)

    code = update_runtime._update_via_tarball(
        tmp_base,
        install_dir=install_dir,
        target_version="6.0.8",
        old_info={"version": "6.0.7"},
    )

    assert code == 0
    assert calls["action"] == "install"
    assert calls["source_dir"] == tmp_base / "ccb_update" / update_runtime._release_extract_dir_name(update_runtime._release_artifact_name())
    assert calls["install_dir"] == install_dir
    assert calls["extra_env"] == {
        "CODEX_INSTALL_PREFIX": str(install_dir),
        "CCB_CLEAN_INSTALL": "1",
    }


def test_update_via_tarball_uses_macos_release_artifact(monkeypatch, tmp_path: Path) -> None:
    tmp_base = tmp_path / "tmp-base"
    tmp_base.mkdir()
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    calls: dict[str, object] = {}
    monkeypatch.setattr(update_runtime.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(update_runtime.platform, "machine", lambda: "arm64")

    def _fake_download(_url: str, destination: Path) -> bool:
        extracted_dir = tmp_base / "payload-src"
        extracted_dir.mkdir(parents=True, exist_ok=True)
        (extracted_dir / "install.sh").write_text("#!/usr/bin/env bash\r\nexit 0\r\n", encoding="utf-8")
        with tarfile.open(destination, "w:gz") as archive:
            archive.add(extracted_dir, arcname="ccb-macos-universal")
        calls["downloaded_to"] = destination
        return True

    monkeypatch.setattr(update_runtime, "download_tarball", _fake_download)
    monkeypatch.setattr(update_runtime, "get_version_info", lambda _install_dir: {"version": "6.0.8"})
    monkeypatch.setattr(update_runtime, "_print_update_outcome", lambda old_info, new_info: None)

    def _fake_run_staged(action: str, *, source_dir: Path, install_dir: Path, extra_env: dict[str, str] | None = None) -> int:
        calls["action"] = action
        calls["source_dir"] = source_dir
        calls["install_dir"] = install_dir
        return 0

    monkeypatch.setattr(update_runtime, "run_staged_unix_installer", _fake_run_staged)

    code = update_runtime._update_via_tarball(
        tmp_base,
        install_dir=install_dir,
        target_version="6.0.8",
        old_info={"version": "6.0.7"},
    )

    assert code == 0
    assert str(calls["downloaded_to"]).endswith("ccb-macos-universal.tar.gz")
    assert calls["action"] == "install"
    assert calls["source_dir"] == tmp_base / "ccb_update" / "ccb-macos-universal"
    assert calls["install_dir"] == install_dir
