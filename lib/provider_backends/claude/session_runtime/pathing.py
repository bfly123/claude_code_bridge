from __future__ import annotations

import time
from pathlib import Path

from project_id import compute_ccb_project_id, normalize_work_dir


def now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def infer_work_dir_from_session_file(session_file: Path) -> Path:
    try:
        parent = Path(session_file).parent
    except Exception:
        return Path.cwd()
    if parent.name == ".ccb":
        return parent.parent
    return parent


def ensure_work_dir_fields(data: dict, *, session_file: Path, fallback_work_dir: Path | None = None) -> None:
    if not isinstance(data, dict):
        return

    work_dir_raw = data.get("work_dir")
    work_dir = work_dir_raw.strip() if isinstance(work_dir_raw, str) else ""
    if not work_dir:
        base = fallback_work_dir or infer_work_dir_from_session_file(session_file)
        work_dir = str(base)
        data["work_dir"] = work_dir

    work_dir_norm_raw = data.get("work_dir_norm")
    work_dir_norm = work_dir_norm_raw.strip() if isinstance(work_dir_norm_raw, str) else ""
    if not work_dir_norm:
        try:
            data["work_dir_norm"] = normalize_work_dir(work_dir)
        except Exception:
            data["work_dir_norm"] = work_dir

    if not str(data.get("ccb_project_id") or "").strip():
        try:
            data["ccb_project_id"] = compute_ccb_project_id(Path(work_dir))
        except Exception:
            pass


__all__ = ["ensure_work_dir_fields", "infer_work_dir_from_session_file", "now_str"]
