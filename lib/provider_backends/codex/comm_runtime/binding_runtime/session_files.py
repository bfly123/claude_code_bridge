from __future__ import annotations

from pathlib import Path

from provider_sessions.files import resolve_project_config_dir


def parse_instance_from_codex_session_name(filename: str) -> str | None:
    name = str(filename or "").strip()
    if not name.startswith(".codex") or not name.endswith("-session"):
        return None
    if name == ".codex-session":
        return None
    middle = name[len(".codex-") : -len("-session")].strip()
    return middle or None


def resolve_unique_codex_session_target(work_dir: Path) -> tuple[Path | None, str | None]:
    root = _normalize_work_dir(work_dir)
    unique = _unique_session_candidates(root)
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


__all__ = ["parse_instance_from_codex_session_name", "resolve_unique_codex_session_target"]
