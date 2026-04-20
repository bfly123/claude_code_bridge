from __future__ import annotations

from pathlib import Path

from provider_sessions.files import resolve_project_config_dir
from provider_backends.codex.session_runtime.follow_policy import codex_session_root_path, has_bound_codex_session
from provider_backends.codex.session_runtime.pathing import read_json

from .session_ids import extract_session_id


def parse_instance_from_codex_session_name(filename: str) -> str | None:
    name = str(filename or "").strip()
    if not name.startswith(".codex") or not name.endswith("-session"):
        return None
    if name == ".codex-session":
        return None
    middle = name[len(".codex-") : -len("-session")].strip()
    return middle or None


def resolve_unique_codex_session_target(work_dir: Path, *, log_path: Path | None = None) -> tuple[Path | None, str | None]:
    root = _normalize_work_dir(work_dir)
    unique = _unique_session_candidates(root)
    if log_path is not None:
        unique = _matching_session_candidates(unique, log_path)
    if len(unique) != 1:
        return (None, None)
    session_file = unique[0]
    return (session_file, parse_instance_from_codex_session_name(session_file.name))


def _normalize_work_dir(work_dir: Path) -> Path:
    try:
        return Path(work_dir).expanduser().resolve()
    except Exception:
        return Path(work_dir).expanduser()


def _candidate_session_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    config_dir = resolve_project_config_dir(root)
    if config_dir.is_dir():
        candidates.extend(sorted(config_dir.glob(".codex*-session")))
    candidates.extend(sorted(root.glob(".codex*-session")))
    return candidates


def _unique_session_candidates(root: Path) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in _candidate_session_files(root):
        if not candidate.is_file():
            continue
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _matching_session_candidates(candidates: list[Path], log_path: Path) -> list[Path]:
    normalized_log_path = _normalize_log_path(log_path)
    if normalized_log_path is None:
        return []
    return [candidate for candidate in candidates if _candidate_matches_log(candidate, normalized_log_path)]


def _candidate_matches_log(candidate: Path, log_path: Path) -> bool:
    data = read_json(candidate)
    current_path = _normalize_log_path(data.get("codex_session_path"))
    if current_path is not None:
        return current_path == log_path
    session_root = codex_session_root_path(data)
    if session_root is not None:
        return _is_within(log_path, session_root)
    current_session_id = str(data.get("codex_session_id") or "").strip()
    if current_session_id:
        return current_session_id == str(extract_session_id(log_path) or "").strip()
    return not has_bound_codex_session(data)


def _normalize_log_path(value: object) -> Path | None:
    if value is None:
        return None
    try:
        return Path(value).expanduser().resolve()
    except Exception:
        try:
            return Path(value).expanduser()
        except Exception:
            return None


def _is_within(path: Path, root: Path) -> bool:
    normalized_path = _normalize_log_path(path)
    normalized_root = _normalize_log_path(root)
    if normalized_path is None or normalized_root is None:
        return False
    try:
        normalized_path.relative_to(normalized_root)
        return True
    except Exception:
        return False


__all__ = ["parse_instance_from_codex_session_name", "resolve_unique_codex_session_target"]
