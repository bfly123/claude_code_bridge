from __future__ import annotations

import os
import re
from pathlib import Path


def normalize_path_for_match(value: str) -> str:
    s = (value or "").strip()
    if os.name == "nt":
        if len(s) >= 4 and s[0] == "/" and s[2] == "/" and s[1].isalpha():
            s = f"{s[1].lower()}:/{s[3:]}"
        match = re.match(r"^/mnt/([A-Za-z])/(.*)$", s)
        if match:
            s = f"{match.group(1).lower()}:/{match.group(2)}"

    try:
        path = Path(s).expanduser()
        normalized = str(path.absolute())
    except Exception:
        normalized = str(value)
    normalized = normalized.replace("\\", "/").rstrip("/")
    if os.name == "nt":
        normalized = normalized.lower()
    return normalized


def path_is_same_or_parent(parent: str, child: str) -> bool:
    parent = normalize_path_for_match(parent)
    child = normalize_path_for_match(child)
    if parent == child:
        return True
    if not parent or not child:
        return False
    if not child.startswith(parent):
        return False
    return child == parent or child[len(parent) :].startswith("/")


def env_truthy(name: str) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def path_matches(expected: str, actual: str, *, allow_parent: bool) -> bool:
    if allow_parent:
        return path_is_same_or_parent(expected, actual)
    return normalize_path_for_match(expected) == normalize_path_for_match(actual)


def is_wsl() -> bool:
    if os.environ.get("WSL_INTEROP") or os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return False


__all__ = [
    "env_truthy",
    "is_wsl",
    "normalize_path_for_match",
    "path_is_same_or_parent",
    "path_matches",
]
