from __future__ import annotations

import os
from pathlib import Path


def _normalize_path_for_match(value: str) -> str:
    text = (value or "").strip()
    if os.name == "nt":
        text = _normalize_windows_match_path(text)
    try:
        normalized = str(Path(text).expanduser().absolute())
    except Exception:
        normalized = str(value or "")
    normalized = normalized.replace("\\", "/").rstrip("/")
    if os.name == "nt":
        normalized = normalized.lower()
    return normalized


def _normalize_windows_match_path(value: str) -> str:
    if len(value) >= 4 and value[0] == "/" and value[2] == "/" and value[1].isalpha():
        return f"{value[1].lower()}:/{value[3:]}"
    if value.startswith("/mnt/") and len(value) > 6:
        drive = value[5]
        if drive.isalpha() and value[6:7] == "/":
            return f"{drive.lower()}:/{value[7:]}"
    return value


def path_is_same_or_parent(parent: str, child: str) -> bool:
    parent_norm = _normalize_path_for_match(parent)
    child_norm = _normalize_path_for_match(child)
    if not parent_norm or not child_norm:
        return False
    if parent_norm == child_norm:
        return True
    if not child_norm.startswith(parent_norm):
        return False
    return child_norm == parent_norm or child_norm[len(parent_norm) :].startswith("/")


__all__ = ["path_is_same_or_parent"]
