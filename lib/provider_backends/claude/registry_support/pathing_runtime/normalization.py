from __future__ import annotations

import os
from pathlib import Path


def normalize_project_path(value: str | Path) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        path = Path(raw).expanduser()
        try:
            path = path.resolve()
        except Exception:
            path = path.absolute()
        raw = str(path)
    except Exception:
        raw = str(value)
    raw = raw.replace("\\", "/").rstrip("/")
    if os.name == "nt":
        raw = raw.lower()
    return raw


def path_within(child: str | Path, parent: str | Path) -> bool:
    normalized_child = normalize_project_path(child)
    normalized_parent = normalize_project_path(parent)
    if not normalized_child or not normalized_parent:
        return False
    if normalized_child == normalized_parent:
        return True
    return normalized_child.startswith(normalized_parent + "/")


__all__ = ["normalize_project_path", "path_within"]
