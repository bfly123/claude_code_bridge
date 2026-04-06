from __future__ import annotations

import json
import time
from pathlib import Path

from provider_core.pathing import find_session_file_for_work_dir, session_filename_for_instance
from project.identity import compute_ccb_project_id, normalize_work_dir
from provider_sessions.files import CCB_PROJECT_CONFIG_DIRNAME


def now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def infer_work_dir_from_session_file(session_file: Path) -> Path:
    try:
        parent = Path(session_file).parent
    except Exception:
        return Path.cwd()
    if parent.name == CCB_PROJECT_CONFIG_DIRNAME:
        return parent.parent
    return parent


def ensure_work_dir_fields(
    data: dict,
    *,
    session_file: Path,
    fallback_work_dir: Path | None = None,
) -> Path | None:
    if not isinstance(data, dict):
        return None

    work_dir = _work_dir_text(data)
    if not work_dir:
        base = fallback_work_dir or infer_work_dir_from_session_file(session_file)
        work_dir = str(base)
        data["work_dir"] = work_dir

    _assign_work_dir_norm(data, work_dir)
    _assign_project_id(data, work_dir)
    try:
        return Path(work_dir)
    except Exception:
        return None


def _work_dir_text(data: dict) -> str:
    work_dir_raw = data.get("work_dir")
    return work_dir_raw.strip() if isinstance(work_dir_raw, str) else ""


def _assign_work_dir_norm(data: dict, work_dir: str) -> None:
    work_dir_norm_raw = data.get("work_dir_norm")
    work_dir_norm = work_dir_norm_raw.strip() if isinstance(work_dir_norm_raw, str) else ""
    if work_dir_norm:
        return
    try:
        data["work_dir_norm"] = normalize_work_dir(work_dir)
    except Exception:
        data["work_dir_norm"] = work_dir


def _assign_project_id(data: dict, work_dir: str) -> None:
    if str(data.get("ccb_project_id") or "").strip():
        return
    try:
        data["ccb_project_id"] = compute_ccb_project_id(Path(work_dir))
    except Exception:
        pass


def find_project_session_file(work_dir: Path, instance: str | None = None) -> Path | None:
    filename = session_filename_for_instance(".claude-session", instance)
    return find_session_file_for_work_dir(work_dir, filename)


def read_json(path: Path) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8-sig")
        data = json.loads(raw)
    except Exception:
        return None
    if isinstance(data, dict) and data:
        return data
    return None


__all__ = [
    "ensure_work_dir_fields",
    "find_project_session_file",
    "infer_work_dir_from_session_file",
    "now_str",
    "read_json",
]
