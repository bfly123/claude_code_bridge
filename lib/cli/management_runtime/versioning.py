from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path


REMOTE_MAIN_COMMIT_API = "https://api.github.com/repos/bfly123/claude_code_bridge/commits/main"
REMOTE_TAGS_API = "https://api.github.com/repos/bfly123/claude_code_bridge/tags"
REPO_URL = "https://github.com/bfly123/claude_code_bridge"


def get_version_info(dir_path: Path) -> dict:
    info = {"commit": None, "date": None, "version": None}
    ccb_file = dir_path / "ccb"
    if ccb_file.exists():
        try:
            content = ccb_file.read_text(encoding="utf-8", errors="replace")
            for line in content.split("\n")[:60]:
                line = line.strip()
                if line.startswith("VERSION") and "=" in line:
                    info["version"] = line.split("=")[1].strip().strip('"').strip("'")
                elif line.startswith("GIT_COMMIT") and "=" in line:
                    value = line.split("=")[1].strip().strip('"').strip("'")
                    if value:
                        info["commit"] = value
                elif line.startswith("GIT_DATE") and "=" in line:
                    value = line.split("=")[1].strip().strip('"').strip("'")
                    if value:
                        info["date"] = value
        except Exception:
            pass
    if shutil.which("git") and (dir_path / ".git").exists():
        result = subprocess.run(
            ["git", "-C", str(dir_path), "log", "-1", "--format=%h|%ci"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split("|")
            if len(parts) >= 2:
                info["commit"] = parts[0]
                info["date"] = parts[1].split()[0]
    return info


def format_version_info(info: dict) -> str:
    parts = []
    if info.get("version"):
        parts.append(f"v{info['version']}")
    if info.get("commit"):
        parts.append(info["commit"])
    if info.get("date"):
        parts.append(info["date"])
    return " ".join(parts) if parts else "unknown"


def get_remote_version_info() -> dict | None:
    import ssl

    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(REMOTE_MAIN_COMMIT_API, headers={"User-Agent": "ccb"})
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            commit = data.get("sha", "")[:7]
            date_str = data.get("commit", {}).get("committer", {}).get("date", "")
            date = date_str[:10] if date_str else None
            return {"commit": commit, "date": date}
    except Exception:
        pass
    if shutil.which("curl"):
        result = subprocess.run(
            ["curl", "-fsSL", REMOTE_MAIN_COMMIT_API],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                commit = data.get("sha", "")[:7]
                date_str = data.get("commit", {}).get("committer", {}).get("date", "")
                date = date_str[:10] if date_str else None
                return {"commit": commit, "date": date}
            except Exception:
                pass
    return None


def get_available_versions() -> list[str]:
    import ssl

    versions: list[str] = []

    def parse_api_response(data):
        result = []
        for tag in data:
            name = tag.get("name", "")
            if name.startswith("v"):
                name = name[1:]
            if re.match(r"^\d+(\.\d+)*$", name):
                result.append(name)
        return result

    def parse_git_refs(output: str):
        result = []
        for line in output.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                ref = parts[1]
                if ref.startswith("refs/tags/v"):
                    name = ref.replace("refs/tags/v", "").rstrip("^{}")
                    if re.match(r"^\d+(\.\d+)*$", name):
                        result.append(name)
        return list(set(result))

    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(REMOTE_TAGS_API, headers={"User-Agent": "ccb"})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            versions = parse_api_response(data)
    except Exception:
        pass
    if not versions and shutil.which("curl"):
        result = subprocess.run(
            ["curl", "-fsSL", REMOTE_TAGS_API],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                versions = parse_api_response(data)
            except Exception:
                pass
    if not versions and shutil.which("git"):
        result = subprocess.run(
            ["git", "ls-remote", "--tags", REPO_URL],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if result.returncode == 0:
            versions = parse_git_refs(result.stdout)
    return versions
