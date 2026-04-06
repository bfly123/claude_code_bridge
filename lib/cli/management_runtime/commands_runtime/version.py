from __future__ import annotations

from pathlib import Path

from ..install import find_install_dir
from ..versioning import format_version_info, get_remote_version_info, get_version_info


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


__all__ = ['cmd_version']
