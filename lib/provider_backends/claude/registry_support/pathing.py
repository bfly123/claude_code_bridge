from __future__ import annotations

import os
import re
from pathlib import Path

from project_id import compute_ccb_project_id, normalize_work_dir
from provider_sessions.files import CCB_PROJECT_CONFIG_DIRNAME


def project_key_for_path(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


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


def candidate_project_paths(work_dir: Path) -> list[str]:
    candidates: list[Path] = []
    env_pwd = os.environ.get("PWD")
    if env_pwd:
        try:
            candidates.append(Path(env_pwd))
        except Exception:
            pass
    candidates.append(work_dir)
    try:
        candidates.append(work_dir.resolve())
    except Exception:
        pass
    out: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = normalize_project_path(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def candidate_project_dirs(root: Path, work_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    env_pwd = os.environ.get("PWD")
    if env_pwd:
        try:
            candidates.append(Path(env_pwd))
        except Exception:
            pass
    candidates.append(work_dir)
    try:
        candidates.append(work_dir.resolve())
    except Exception:
        pass

    out: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = project_key_for_path(candidate)
        if key in seen:
            continue
        seen.add(key)
        out.append(root / key)
    return out


def path_within(child: str, parent: str) -> bool:
    try:
        child_path = Path(child).expanduser()
        parent_path = Path(parent).expanduser()
        try:
            child_path = child_path.resolve()
        except Exception:
            child_path = child_path.absolute()
        try:
            parent_path = parent_path.resolve()
        except Exception:
            parent_path = parent_path.absolute()
        child = str(child_path)
        parent = str(parent_path)
    except Exception:
        pass
    if os.name == "nt":
        child = child.lower().replace("\\", "/")
        parent = parent.lower().replace("\\", "/")
    else:
        child = child.replace("\\", "/")
        parent = parent.replace("\\", "/")
    child = child.rstrip("/")
    parent = parent.rstrip("/")
    if child == parent:
        return True
    return child.startswith(parent + "/")


def infer_work_dir_from_session_file(session_file: Path) -> Path:
    try:
        parent = Path(session_file).parent
    except Exception:
        return Path.cwd()
    if parent.name == CCB_PROJECT_CONFIG_DIRNAME:
        return parent.parent
    return parent


def ensure_claude_session_work_dir_fields(payload: dict, session_file: Path) -> Path | None:
    if not isinstance(payload, dict):
        return None

    work_dir_path: Path | None = None
    raw_work_dir = payload.get("work_dir")
    if isinstance(raw_work_dir, str) and raw_work_dir.strip():
        try:
            work_dir_path = Path(raw_work_dir.strip())
        except Exception:
            work_dir_path = None
    if work_dir_path is None:
        work_dir_path = infer_work_dir_from_session_file(session_file)
    if work_dir_path is None:
        return None

    work_dir_str = str(work_dir_path)
    payload["work_dir"] = work_dir_str

    raw_norm = payload.get("work_dir_norm")
    if not isinstance(raw_norm, str) or not raw_norm.strip():
        try:
            payload["work_dir_norm"] = normalize_work_dir(work_dir_str)
        except Exception:
            payload["work_dir_norm"] = work_dir_str

    if not str(payload.get("ccb_project_id") or "").strip():
        try:
            payload["ccb_project_id"] = compute_ccb_project_id(work_dir_path)
        except Exception:
            pass

    return work_dir_path
