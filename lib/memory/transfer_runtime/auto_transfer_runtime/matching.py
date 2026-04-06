from __future__ import annotations

from pathlib import Path


def normalize_path_for_match(value: Path) -> str:
    try:
        from project.identity import normalize_work_dir
    except Exception:
        normalize_work_dir = None
    try:
        if normalize_work_dir:
            return normalize_work_dir(value)
    except Exception:
        pass
    try:
        return str(Path(value).expanduser().resolve())
    except Exception:
        try:
            return str(Path(value).expanduser().absolute())
        except Exception:
            return str(value)


def is_current_work_dir(work_dir: Path) -> bool:
    try:
        cwd = Path.cwd()
    except Exception:
        cwd = Path(".")
    return normalize_path_for_match(cwd) == normalize_path_for_match(work_dir)


__all__ = ['is_current_work_dir', 'normalize_path_for_match']
