from __future__ import annotations

import importlib.util
from pathlib import Path
import tarfile


def _load_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "build_macos_release.py"
    spec = importlib.util.spec_from_file_location("build_macos_release", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_macos_release_artifact_is_universal() -> None:
    module = _load_module()

    assert module.release_artifact_basename("macos", machine="x86_64") == "ccb-macos-universal"
    assert module.release_artifact_basename("macos", machine="arm64") == "ccb-macos-universal"
    assert module.release_build_arch("macos", machine="x86_64") == "universal"


def test_macos_create_tarball_includes_legacy_update_alias(tmp_path: Path) -> None:
    module = _load_module()
    stage_root = tmp_path / "stage"
    artifact_root = stage_root / "ccb-macos-universal"
    artifact_root.mkdir(parents=True)
    (artifact_root / "install.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    artifact_path = tmp_path / "ccb-macos-universal.tar.gz"

    module.create_tarball(stage_root=stage_root, artifact_root=artifact_root, artifact_path=artifact_path)

    with tarfile.open(artifact_path, "r:gz") as archive:
        install_member = archive.getmember("ccb-macos-universal/install.sh")
        alias_member = archive.getmember("ccb-macos-universal.tar.gz")

    assert install_member.isfile()
    assert alias_member.issym()
    assert alias_member.linkname == "ccb-macos-universal"
