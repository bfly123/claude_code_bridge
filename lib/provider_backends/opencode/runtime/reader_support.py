from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from opencode_runtime.paths import (
    compute_opencode_project_id,
    env_truthy,
    normalize_path_for_match,
    path_matches,
)


def build_work_dir_candidates(work_dir: Path) -> list[str]:
    candidates: list[str] = []
    raw_pwd = (os.environ.get("PWD") or "").strip()
    if raw_pwd:
        candidates.append(raw_pwd)
    candidates.append(str(work_dir))
    try:
        candidates.append(str(work_dir.resolve()))
    except Exception:
        pass
    seen: set[str] = set()
    out: list[str] = []
    for candidate in candidates:
        norm = normalize_path_for_match(candidate)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def detect_project_id_for_workdir(
    *,
    storage_root: Path,
    work_dir: Path,
    load_json_fn,
    allow_parent_match: bool,
) -> Optional[str]:
    projects_dir = Path(storage_root).expanduser() / "project"
    if not projects_dir.exists():
        return None

    work_candidates = build_work_dir_candidates(work_dir)
    best_id: str | None = None
    best_score: tuple[int, int, float] = (-1, -1, -1.0)

    try:
        paths = [p for p in projects_dir.glob("*.json") if p.is_file()]
    except Exception:
        paths = []

    for path in paths:
        payload = load_json_fn(path)

        pid = payload.get("id") if isinstance(payload.get("id"), str) and payload.get("id") else path.stem
        worktree = payload.get("worktree")
        if not isinstance(pid, str) or not pid:
            continue
        if not isinstance(worktree, str) or not worktree:
            continue

        worktree_norm = normalize_path_for_match(worktree)
        if not worktree_norm:
            continue

        if not any(path_matches(worktree_norm, candidate, allow_parent=allow_parent_match) for candidate in work_candidates):
            continue

        updated = (payload.get("time") or {}).get("updated")
        try:
            updated_i = int(updated)
        except Exception:
            updated_i = -1
        try:
            mtime = path.stat().st_mtime
        except Exception:
            mtime = 0.0

        score = (len(worktree_norm), updated_i, mtime)
        if score > best_score:
            best_id = pid
            best_score = score

    return best_id


def fallback_project_id(work_dir: Path) -> str:
    return compute_opencode_project_id(work_dir)


def allow_parent_workdir_match() -> bool:
    return env_truthy("OPENCODE_ALLOW_PARENT_WORKDIR_MATCH")


def allow_git_root_fallback() -> bool:
    return env_truthy("OPENCODE_ALLOW_GIT_ROOT_FALLBACK")


def allow_any_session() -> bool:
    return env_truthy("OPENCODE_ALLOW_ANY_SESSION")


def allow_session_rollover() -> bool:
    return env_truthy("OPENCODE_ALLOW_SESSION_ROLLOVER")
