from __future__ import annotations

from pathlib import Path

from ..install import find_install_dir
from ..versioning import format_version_info, get_available_versions, get_remote_version_info, get_version_info
from .matching import is_newer_version, latest_version


def cmd_version(args, *, script_root: Path) -> int:
    del args
    install_dir = find_install_dir(script_root)
    local_info = get_version_info(install_dir)
    local_str = format_version_info(local_info)
    install_mode = local_info.get("install_mode") or "unknown"
    source_kind = local_info.get("source_kind") or "unknown"
    channel = local_info.get("channel") or "unknown"

    print(f"ccb (Claude Code Bridge) {local_str}")
    print(f"Install path: {install_dir}")
    print(f"Install mode: {install_mode}")
    print(f"Install source: {source_kind}")
    print(f"Channel: {channel}")
    if local_info.get("platform") or local_info.get("arch") or local_info.get("build_time"):
        print(
            "Build: "
            f"{local_info.get('platform') or 'unknown'} "
            f"{local_info.get('arch') or 'unknown'} "
            f"{local_info.get('build_time') or 'unknown'}"
        )

    print("\nChecking for updates...")
    if _is_source_install(local_info=local_info, install_dir=install_dir):
        _print_source_update_status(local_info)
    elif (install_dir / ".git").exists():
        _print_git_update_status(local_info)
    else:
        _print_release_update_status(local_info)
    return 0


def _is_source_install(*, local_info: dict[str, object], install_dir: Path) -> bool:
    if str(local_info.get("install_mode") or "").strip() == "source":
        return True
    if str(local_info.get("source_kind") or "").strip() == "source":
        return True
    return (install_dir / ".git").exists()


def _print_source_update_status(local_info: dict[str, object]) -> None:
    remote_info = get_remote_version_info()
    if remote_info is None:
        print("⚠️  Unable to check source updates (network error)")
        print("   Run: ccb update  to install the latest stable release")
        return
    if local_info.get("commit") and remote_info.get("commit"):
        if local_info["commit"] == remote_info["commit"]:
            print("✅ Up to date")
            print("   Run: ccb update  to switch this install to the latest stable release")
            return
        remote_str = f"{remote_info['commit']} {remote_info.get('date', '')}".strip()
        print(f"📦 Source update available: {remote_str}")
        print("   Use: git pull  (or switch commits in your checkout)")
        print("   Rerun: ./install.sh install  if you want the global install to stay in source/dev mode")
        print("   Run: ccb update  to switch the global install to the latest stable release")
        return
    print("⚠️  Unable to compare source revisions")
    print("   Run: ccb update  to install the latest stable release")


def _print_git_update_status(local_info: dict[str, object]) -> None:
    remote_info = get_remote_version_info()
    if remote_info is None:
        print("⚠️  Unable to check for updates (network error)")
        return
    if local_info.get("commit") and remote_info.get("commit"):
        if local_info["commit"] == remote_info["commit"]:
            print("✅ Up to date")
            return
        remote_str = f"{remote_info['commit']} {remote_info.get('date', '')}".strip()
        print(f"📦 Update available: {remote_str}")
        print("   Run: ccb update")
        return
    print("⚠️  Unable to compare versions")


def _print_release_update_status(local_info: dict[str, object]) -> None:
    versions = get_available_versions()
    latest = latest_version(versions)
    current = str(local_info.get("version") or "").strip()
    if not latest:
        print("⚠️  Unable to check release updates")
        return
    if current and not is_newer_version(latest, current):
        print(f"✅ Up to date (latest release: v{latest})")
        return
    if current:
        print(f"📦 Release update available: v{latest}")
        print("   Run: ccb update")
        return
    print(f"📦 Latest release: v{latest}")
    print("   Run: ccb update")


__all__ = ['cmd_version']
