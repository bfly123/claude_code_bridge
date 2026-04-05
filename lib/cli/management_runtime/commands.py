from __future__ import annotations

import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile

from .cleanup import cleanup_claude_files
from .install import download_tarball, find_install_dir, pick_temp_base_dir, run_installer, safe_extract_tar
from .versioning import REPO_URL, format_version_info, get_available_versions, get_remote_version_info, get_version_info


def find_matching_version(target: str, versions: list[str]) -> str | None:
    target_parts = target.split(".")

    def version_key(version: str):
        parts = version.split(".")
        return tuple(int(part) for part in parts if part.isdigit())

    matching = []
    for version in versions:
        version_parts = version.split(".")
        if len(version_parts) >= len(target_parts) and version_parts[: len(target_parts)] == target_parts:
            matching.append(version)
    if not matching:
        return None
    matching.sort(key=version_key, reverse=True)
    return matching[0]


def cmd_version(args, *, script_root: Path) -> int:
    del args
    install_dir = find_install_dir(script_root)
    local_info = get_version_info(install_dir)
    local_str = format_version_info(local_info)

    print(f"ccb (Claude Code Bridge) {local_str}")
    print(f"Install path: {install_dir}")

    print("\nChecking for updates...")
    remote_info = get_remote_version_info()
    if remote_info is None:
        print("⚠️  Unable to check for updates (network error)")
    elif local_info.get("commit") and remote_info.get("commit"):
        if local_info["commit"] == remote_info["commit"]:
            print("✅ Up to date")
        else:
            remote_str = f"{remote_info['commit']} {remote_info.get('date', '')}"
            print(f"📦 Update available: {remote_str}")
            print("   Run: ccb update")
    else:
        print("⚠️  Unable to compare versions")
    return 0


def cmd_update(args, *, script_root: Path) -> int:
    default_install_dir = Path.home() / ".local/share/codex-dual"
    install_dir = Path(os.environ.get("CODEX_INSTALL_PREFIX") or default_install_dir).expanduser()
    if (script_root / "install.sh").exists():
        install_dir = script_root

    target_version = None
    if hasattr(args, "target") and args.target:
        target_spec = args.target.lstrip("v")
        if re.match(r"^\d+(\.\d+)*$", target_spec):
            print(f"🔍 Looking for version matching: {target_spec}")
            versions = get_available_versions()
            if not versions:
                print("❌ Could not fetch available versions")
                return 1
            target_version = find_matching_version(target_spec, versions)
            if not target_version:
                ordered = sorted(versions, key=lambda item: [int(x) for x in item.split(".")], reverse=True)[:10]
                print(f"❌ No version found matching '{target_spec}'")
                print(f"   Available: {', '.join(ordered)}")
                return 1
            print(f"📌 Target version: v{target_version}")
        else:
            print(f"❌ Invalid version format: {args.target}")
            print("   Examples: ccb update 4, ccb update 4.1, ccb update 4.1.3")
            return 1

    old_info = get_version_info(install_dir)
    if target_version:
        print(f"🔄 Updating to v{target_version}...")
    else:
        print("🔄 Checking for updates...")

    if shutil.which("git") and (install_dir / ".git").exists():
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
        if result.returncode == 0:
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
            old_str = format_version_info(old_info)
            new_str = format_version_info(new_info)
            if old_info.get("commit") != new_info.get("commit"):
                print(f"✅ Updated: {old_str} → {new_str}")
            else:
                print(f"✅ Already up to date: {new_str}")
            return 0
        err_msg = "Git checkout failed" if target_version else "Git pull failed"
        print(f"⚠️ {err_msg}: {result.stderr.strip()}")
        print("Falling back to tarball download...")

    try:
        tmp_base = pick_temp_base_dir(install_dir)
    except Exception as exc:
        print(str(exc))
        return 1

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
        old_str = format_version_info(old_info)
        new_str = format_version_info(new_info)
        if old_info.get("commit") != new_info.get("commit") or old_info.get("version") != new_info.get("version"):
            print(f"✅ Updated: {old_str} → {new_str}")
        else:
            print(f"✅ Already up to date: {new_str}")
        return 0
    except Exception as exc:
        print(f"❌ Update failed: {exc}")
        return 1
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


def cmd_uninstall(_args, *, script_root: Path) -> int:
    cleanup_claude_files()
    return run_installer("uninstall", script_root=script_root)


def cmd_reinstall(_args, *, script_root: Path) -> int:
    cleanup_claude_files()
    return run_installer("install", script_root=script_root)
