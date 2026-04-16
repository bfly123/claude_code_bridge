from __future__ import annotations

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


def test_cmd_update_rejects_non_linux_platform(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(update_runtime.platform, "system", lambda: "Darwin")

    code = update_runtime.cmd_update(SimpleNamespace(target=None), script_root=tmp_path / "script-root")

    assert code == 1
    captured = capsys.readouterr()
    assert "Linux/WSL" in captured.out


def test_release_artifact_name_uses_linux_arch_aliases(monkeypatch) -> None:
    monkeypatch.setattr(update_runtime.platform, "machine", lambda: "amd64")
    assert update_runtime._release_artifact_name() == "ccb-linux-x86_64.tar.gz"

    monkeypatch.setattr(update_runtime.platform, "machine", lambda: "arm64")
    assert update_runtime._release_artifact_name() == "ccb-linux-aarch64.tar.gz"


def test_release_artifact_url_points_to_release_download() -> None:
    url = update_runtime._release_artifact_url("6.0.0", artifact_name="ccb-linux-x86_64.tar.gz")

    assert url == "https://github.com/bfly123/claude_code_bridge/releases/download/v6.0.0/ccb-linux-x86_64.tar.gz"
