from __future__ import annotations

from pathlib import Path
from typing import Any

from project_id import normalize_work_dir as _normalize_work_dir_impl

from .binding import extract_cwd_from_log_file


def normalize_path(value: Any | None) -> Path | None:
    if value in (None, ""):
        return None
    if isinstance(value, Path):
        return value
    try:
        return Path(value).expanduser()
    except TypeError:
        return None


def normalize_work_dir(work_dir: Path | None) -> str | None:
    if work_dir is None:
        work_dir = Path.cwd()
    try:
        normalized = _normalize_work_dir_impl(work_dir)
    except Exception:
        return None
    return normalized or None


def extract_cwd_from_log(reader, log_path: Path) -> str | None:
    del reader
    cwd = extract_cwd_from_log_file(log_path)
    if not cwd:
        return None
    try:
        normalized = _normalize_work_dir_impl(cwd)
    except Exception:
        return None
    return normalized or None


__all__ = ["extract_cwd_from_log", "normalize_path", "normalize_work_dir"]
