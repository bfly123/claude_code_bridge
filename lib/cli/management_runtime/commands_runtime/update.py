from __future__ import annotations

import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile

from ..install import download_tarball, pick_temp_base_dir, safe_extract_tar
from ..versioning import REPO_URL, format_version_info, get_available_versions, get_version_info
from .matching import find_matching_version, latest_version


def cmd_update(args, *, script_root: Path) -> int:
    supported, reason = _supported_update_platform()
    if not supported:
        print(reason)
        return 1

    default_install_dir = Path.home() / ".local/share/codex-dual"
    install_dir = Path(os.environ.get("CODEX_INSTALL_PREFIX") or default_install_dir).expanduser()
    if (script_root / "install.sh").exists():
        install_dir = script_root

    target_version = _resolve_target_version(args)
    if target_version is False:
        return 1

    old_info = get_version_info(install_dir)
    if target_version:
        print(f"🔄 Updating to v{target_version}...")
    else:
        print("🔄 Checking for release updates...")

    try:
        tmp_base = pick_temp_base_dir(install_dir)
    except Exception as exc:
        print(str(exc))
        return 1
    resolved_target = target_version or _resolve_latest_release_version()
    if not resolved_target:
        print("❌ Could not determine latest release version")
        return 1
    return _update_via_tarball(tmp_base, install_dir=install_dir, target_version=resolved_target, old_info=old_info)


def _resolve_target_version(args) -> str | bool | None:
    if not hasattr(args, "target") or not args.target:
        return None
    target_spec = args.target.lstrip("v")
    if not re.match(r"^\d+(\.\d+)*$", target_spec):
        print(f"❌ Invalid version format: {args.target}")
        print("   Examples: ccb update 4, ccb update 4.1, ccb update 4.1.3")
        return False
    print(f"🔍 Looking for version matching: {target_spec}")
    versions = get_available_versions()
    if not versions:
        print("❌ Could not fetch available versions")
        return False
    target_version = find_matching_version(target_spec, versions)
    if not target_version:
        ordered = sorted(versions, key=lambda item: [int(x) for x in item.split(".")], reverse=True)[:10]
        print(f"❌ No version found matching '{target_spec}'")
        print(f"   Available: {', '.join(ordered)}")
        return False
    print(f"📌 Target version: v{target_version}")
    return target_version


def _supported_update_platform() -> tuple[bool, str | None]:
    system_name = platform.system()
    if system_name == "Linux":
        return True, None
    return (
        False,
        "❌ `ccb update` is currently supported only on Linux/WSL.\n"
        "   Please use a Linux/WSL runtime, or reinstall manually on this platform.",
    )


def _resolve_latest_release_version() -> str | None:
    versions = get_available_versions()
    return latest_version(versions)


def _update_via_tarball(tmp_base: Path, *, install_dir: Path, target_version: str | None, old_info: dict[str, object]) -> int:
    if not target_version:
        print("❌ Update failed: no release version selected")
        return 1
    artifact_name = _release_artifact_name()
    if not artifact_name:
        print(f"❌ Update failed: unsupported Linux architecture '{platform.machine()}'")
        return 1
    tarball_url = _release_artifact_url(target_version, artifact_name=artifact_name)
    extracted_name = artifact_name

    tmp_dir = tmp_base / "ccb_update"
    try:
        print(f"📥 Downloading v{target_version}...")
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tarball_path = tmp_dir / artifact_name
        if not download_tarball(tarball_url, tarball_path):
            print("❌ Update failed: unable to download release tarball")
            return 1

        print("📂 Extracting...")
        with tarfile.open(tarball_path, "r:gz") as tar:
            safe_extract_tar(tar, tmp_dir)
        extracted_dir = tmp_dir / extracted_name

        print("🔧 Installing...")
        env = os.environ.copy()
        env["CODEX_INSTALL_PREFIX"] = str(install_dir)
        env["CCB_CLEAN_INSTALL"] = "1"
        bash_bin = shutil.which("bash")
        if not bash_bin:
            print("❌ Update failed: required shell 'bash' is not available")
            return 1
        subprocess.run([bash_bin, str(extracted_dir / "install.sh"), "install"], check=True, env=env)

        new_info = get_version_info(install_dir)
        _print_update_outcome(old_info, new_info)
        return 0
    except Exception as exc:
        print(f"❌ Update failed: {exc}")
        return 1
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _print_update_outcome(old_info: dict[str, object], new_info: dict[str, object]) -> None:
    old_str = format_version_info(old_info)
    new_str = format_version_info(new_info)
    if old_info.get("commit") != new_info.get("commit") or old_info.get("version") != new_info.get("version"):
        print(f"✅ Updated: {old_str} → {new_str}")
    else:
        print(f"✅ Already up to date: {new_str}")


def _release_artifact_url(version: str, *, artifact_name: str) -> str:
    return f"{REPO_URL}/releases/download/v{version}/{artifact_name}"


def _release_artifact_name() -> str | None:
    arch = _normalize_linux_arch(platform.machine())
    if arch is None:
        return None
    return f"ccb-linux-{arch}.tar.gz"


def _normalize_linux_arch(raw_arch: str) -> str | None:
    text = str(raw_arch or "").strip().lower()
    mapping = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
    }
    return mapping.get(text)


__all__ = ['cmd_update']
