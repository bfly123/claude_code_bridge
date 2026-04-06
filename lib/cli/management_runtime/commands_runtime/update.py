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
from .matching import find_matching_version


def cmd_update(args, *, script_root: Path) -> int:
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
        print("🔄 Checking for updates...")

    git_result = _try_git_update(install_dir, target_version=target_version, old_info=old_info)
    if git_result is not None:
        return git_result

    try:
        tmp_base = pick_temp_base_dir(install_dir)
    except Exception as exc:
        print(str(exc))
        return 1
    return _update_via_tarball(tmp_base, install_dir=install_dir, target_version=target_version, old_info=old_info)


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


def _try_git_update(install_dir: Path, *, target_version: str | None, old_info: dict[str, object]) -> int | None:
    if not (shutil.which("git") and (install_dir / ".git").exists()):
        return None
    if target_version:
        print(f"📦 Switching to v{target_version} via git...")
        subprocess.run(
            ["git", "-C", str(install_dir), "fetch", "--tags", "--force"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        result = subprocess.run(
            ["git", "-C", str(install_dir), "checkout", f"v{target_version}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    else:
        print("📦 Updating via git pull...")
        result = subprocess.run(
            ["git", "-C", str(install_dir), "pull", "--ff-only"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    if result.returncode != 0:
        err_msg = "Git checkout failed" if target_version else "Git pull failed"
        print(f"⚠️ {err_msg}: {result.stderr.strip()}")
        print("Falling back to tarball download...")
        return None

    print(result.stdout.strip() if result.stdout.strip() else "Already up to date.")
    print("🔧 Reinstalling...")
    env = os.environ.copy()
    env["CCB_CLEAN_INSTALL"] = "1"
    if platform.system() == "Windows":
        subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(install_dir / "install.ps1"), "install"],
            env=env,
        )
    else:
        subprocess.run([str(install_dir / "install.sh"), "install"], env=env)
    new_info = get_version_info(install_dir)
    _print_update_outcome(old_info, new_info)
    return 0


def _update_via_tarball(tmp_base: Path, *, install_dir: Path, target_version: str | None, old_info: dict[str, object]) -> int:
    if target_version:
        tarball_url = f"{REPO_URL}/archive/refs/tags/v{target_version}.tar.gz"
        extracted_name = f"claude_code_bridge-{target_version}"
    else:
        tarball_url = f"{REPO_URL}/archive/refs/heads/main.tar.gz"
        extracted_name = "claude_code_bridge-main"

    tmp_dir = tmp_base / "ccb_update"
    try:
        print(f"📥 Downloading {'v' + target_version if target_version else 'latest version'}...")
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tarball_path = tmp_dir / "main.tar.gz"
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
        if platform.system() == "Windows":
            subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(extracted_dir / "install.ps1"), "install"],
                check=True,
                env=env,
            )
        else:
            subprocess.run([str(extracted_dir / "install.sh"), "install"], check=True, env=env)

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


__all__ = ['cmd_update']
