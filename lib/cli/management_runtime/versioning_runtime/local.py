from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def get_version_info(dir_path: Path) -> dict:
    info = {"commit": None, "date": None, "version": None}
    info.update(read_embedded_version_info(dir_path / "ccb"))
    git_info = git_version_info(dir_path)
    if git_info is not None:
        info.update(git_info)
    return info


def read_embedded_version_info(ccb_file: Path) -> dict[str, str | None]:
    if not ccb_file.exists():
        return {}
    try:
        content = ccb_file.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    info: dict[str, str | None] = {}
    for line in content.split("\n")[:60]:
        key, value = version_assignment(line)
        if key is None or not value:
            continue
        info[key] = value
    return info


def version_assignment(line: str) -> tuple[str | None, str | None]:
    text = line.strip()
    if "=" not in text:
        return None, None
    name, raw_value = text.split("=", 1)
    value = raw_value.strip().strip('"').strip("'")
    mapping = {
        "VERSION": "version",
        "GIT_COMMIT": "commit",
        "GIT_DATE": "date",
    }
    return mapping.get(name.strip()), value or None


def git_version_info(dir_path: Path) -> dict[str, str] | None:
    if not shutil.which("git") or not (dir_path / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(dir_path), "log", "-1", "--format=%h|%ci"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    parts = result.stdout.strip().split("|")
    if len(parts) < 2:
        return None
    return {
        "commit": parts[0],
        "date": parts[1].split()[0],
    }


def format_version_info(info: dict) -> str:
    parts = []
    if info.get("version"):
        parts.append(f"v{info['version']}")
    if info.get("commit"):
        parts.append(info["commit"])
    if info.get("date"):
        parts.append(info["date"])
    return " ".join(parts) if parts else "unknown"


__all__ = ['format_version_info', 'get_version_info']
