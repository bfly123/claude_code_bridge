from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Optional


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
        pass
    raw = raw.replace("\\", "/").rstrip("/")
    if os.name == "nt":
        raw = raw.lower()
    return raw


def project_root_marker(project_dir: Path) -> str:
    marker = Path(project_dir).expanduser() / ".project_root"
    if not marker.is_file():
        return ""
    try:
        return normalize_project_path(marker.read_text(encoding="utf-8").strip())
    except Exception:
        return ""


def slugify_project_hash(name: str) -> str:
    text = (name or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def compute_project_hashes(work_dir: Optional[Path] = None) -> tuple[str, str]:
    path = work_dir or Path.cwd()
    try:
        abs_path = path.expanduser().absolute()
    except Exception:
        abs_path = path
    basename_hash = slugify_project_hash(abs_path.name)
    sha256_hash = hashlib.sha256(str(abs_path).encode()).hexdigest()
    return basename_hash, sha256_hash


__all__ = [
    'compute_project_hashes',
    'normalize_project_path',
    'project_root_marker',
    'slugify_project_hash',
]
