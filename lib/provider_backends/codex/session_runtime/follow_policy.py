from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from provider_sessions.files import resolve_project_config_dir

from .pathing import read_json


def codex_home_path(data: Mapping[str, object] | None) -> Path | None:
    if not isinstance(data, Mapping):
        return None
    return _normalize_path(data.get("codex_home"))


def codex_session_root_path(data: Mapping[str, object] | None) -> Path | None:
    if not isinstance(data, Mapping):
        return None
    codex_home = codex_home_path(data)
    if codex_home is not None:
        return codex_home / "sessions"
    root = _normalize_path(data.get("codex_session_root"))
    if root is not None:
        return root
    return None


def has_bound_codex_session(data: Mapping[str, object] | None) -> bool:
    if not isinstance(data, Mapping):
        return False
    if str(data.get("codex_session_id") or "").strip():
        return True
    return bool(str(data.get("codex_session_path") or "").strip())


def should_follow_workspace_sessions(
    *, work_dir: Path | None, session_file: Path | None, session_data: Mapping[str, object] | None = None
) -> bool:
    normalized_work_dir = _normalize_path(work_dir)
    if normalized_work_dir is None:
        return False
    if has_bound_codex_session(session_data):
        return False
    if session_file is None:
        return True

    matching_files = _session_files_for_work_dir(normalized_work_dir)
    if not matching_files:
        return True

    normalized_session_file = _normalize_path(session_file)
    if normalized_session_file is None:
        return len(matching_files) == 1
    return len(matching_files) == 1 and normalized_session_file in matching_files


def _session_files_for_work_dir(work_dir: Path) -> set[Path]:
    matches: set[Path] = set()
    for candidate in _candidate_session_files(work_dir):
        candidate_work_dir = _candidate_work_dir(candidate)
        if candidate_work_dir == work_dir:
            matches.add(candidate)
    return matches


def _candidate_session_files(work_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for root in (resolve_project_config_dir(work_dir), work_dir):
        if not root.is_dir():
            continue
        for candidate in sorted(root.glob(".codex*-session")):
            normalized_candidate = _normalize_path(candidate)
            if normalized_candidate is None or normalized_candidate in seen or not normalized_candidate.is_file():
                continue
            seen.add(normalized_candidate)
            candidates.append(normalized_candidate)
    return candidates


def _candidate_work_dir(session_file: Path) -> Path | None:
    data = read_json(session_file)
    raw = (
        data.get("work_dir")
        or data.get("work_dir_norm")
        or data.get("workspace_path")
        or data.get("start_dir")
    )
    return _normalize_path(raw)


def _normalize_path(value: object) -> Path | None:
    if value is None:
        return None
    try:
        return Path(value).expanduser().resolve()
    except Exception:
        try:
            return Path(value).expanduser()
        except Exception:
            return None


__all__ = ["codex_home_path", "codex_session_root_path", "has_bound_codex_session", "should_follow_workspace_sessions"]
