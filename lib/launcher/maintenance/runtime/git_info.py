from __future__ import annotations

from pathlib import Path
import subprocess


def get_git_info(script_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(script_root), "log", "-1", "--format=%h %ci"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""
