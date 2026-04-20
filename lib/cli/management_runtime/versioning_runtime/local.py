from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def get_version_info(dir_path: Path) -> dict:
    info = {
        "commit": None,
        "date": None,
        "version": None,
        "build_time": None,
        "platform": None,
        "arch": None,
        "channel": None,
        "source_kind": None,
        "install_mode": None,
        "installed_at": None,
    }
    info.update(read_build_info(dir_path / "BUILD_INFO.json"))
    info.update(read_version_file(dir_path / "VERSION"))
    info.update(read_embedded_version_info(dir_path / "ccb"))
    git_info = git_version_info(dir_path)
    if git_info is not None:
        info.update(git_info)
    info = normalize_installation_info(info, dir_path=dir_path)
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


def read_version_file(version_file: Path) -> dict[str, str | None]:
    if not version_file.exists():
        return {}
    try:
        value = version_file.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return {}
    if not value:
        return {}
    return {"version": value}


def read_build_info(build_info_file: Path) -> dict[str, str | None]:
    if not build_info_file.exists():
        return {}
    try:
        payload = json.loads(build_info_file.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, str | None] = {}
    for key in (
        "version",
        "commit",
        "date",
        "build_time",
        "platform",
        "arch",
        "channel",
        "source_kind",
        "install_mode",
        "installed_at",
    ):
        value = payload.get(key)
        normalized[key] = str(value).strip() if value not in (None, "") else None
    return normalized


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


def normalize_installation_info(info: dict, *, dir_path: Path) -> dict:
    normalized = dict(info)
    if not normalized.get("install_mode"):
        normalized["install_mode"] = "source" if (dir_path / ".git").exists() else "release"
    if not normalized.get("source_kind"):
        normalized["source_kind"] = "source" if (dir_path / ".git").exists() else "release"
    if not normalized.get("channel"):
        normalized["channel"] = "dev" if (dir_path / ".git").exists() else None
    return normalized


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
