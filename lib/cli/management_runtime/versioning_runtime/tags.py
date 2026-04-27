from __future__ import annotations

import re
import shutil
import subprocess

from .constants import REMOTE_TAGS_API, REPO_URL
from .transport import fetch_json_via_curl, fetch_json_via_urllib


def get_available_versions(
    *,
    urllib_timeout: float = 10,
    curl_timeout: float = 15,
    git_timeout: float = 30,
) -> list[str]:
    versions: list[str] = []

    try:
        data = fetch_json_via_urllib(REMOTE_TAGS_API, timeout=float(urllib_timeout))
    except Exception:
        data = None
    if isinstance(data, list):
        versions = parse_api_response(data)
    if not versions:
        data = fetch_json_via_curl(REMOTE_TAGS_API, timeout=float(curl_timeout))
        if isinstance(data, list):
            versions = parse_api_response(data)
    if not versions and shutil.which("git"):
        result = subprocess.run(
            ["git", "ls-remote", "--tags", REPO_URL],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=float(git_timeout),
        )
        if result.returncode == 0:
            versions = parse_git_refs(result.stdout)
    return versions


def parse_api_response(data) -> list[str]:
    result = []
    for tag in data:
        name = tag.get("name", "")
        if name.startswith("v"):
            name = name[1:]
        if re.match(r"^\d+(\.\d+)*$", name):
            result.append(name)
    return result


def parse_git_refs(output: str) -> list[str]:
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


__all__ = ['get_available_versions', 'parse_api_response', 'parse_git_refs']
