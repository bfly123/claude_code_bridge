from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from provider_sessions.files import resolve_project_config_dir

SESSION_ID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def extract_cwd_from_log_file(log_path: Path) -> Optional[str]:
    try:
        with log_path.open("r", encoding="utf-8") as handle:
            first_line = handle.readline()
    except Exception:
        return None
    if not first_line:
        return None
    try:
        entry = json.loads(first_line)
    except Exception:
        return None
    if entry.get("type") != "session_meta":
        return None
    payload = entry.get("payload", {})
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    if isinstance(cwd, str) and cwd.strip():
        return cwd.strip()
    return None


def parse_instance_from_codex_session_name(filename: str) -> Optional[str]:
    name = str(filename or "").strip()
    if not name.startswith(".codex") or not name.endswith("-session"):
        return None
    if name == ".codex-session":
        return None
    middle = name[len(".codex-"):-len("-session")]
    middle = middle.strip()
    return middle or None


def resolve_unique_codex_session_target(work_dir: Path) -> tuple[Optional[Path], Optional[str]]:
    """Return the only Codex session file for a project, or (None, None) if ambiguous."""
    try:
        root = Path(work_dir).expanduser().resolve()
    except Exception:
        root = Path(work_dir).expanduser()

    candidates: list[Path] = []
    config_dir = resolve_project_config_dir(root)
    if config_dir.is_dir():
        candidates.extend(sorted(config_dir.glob(".codex*-session")))
    candidates.extend(sorted(root.glob(".codex*-session")))

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate.is_file():
            continue
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)

    if len(unique) != 1:
        return (None, None)

    session_file = unique[0]
    return (session_file, parse_instance_from_codex_session_name(session_file.name))


def extract_session_id(log_path: Path) -> Optional[str]:
    for source in (log_path.stem, log_path.name):
        match = SESSION_ID_PATTERN.search(source)
        if match:
            return match.group(0)

    try:
        with log_path.open("r", encoding="utf-8") as handle:
            first_line = handle.readline()
    except OSError:
        return None

    if not first_line:
        return None

    match = SESSION_ID_PATTERN.search(first_line)
    if match:
        return match.group(0)

    try:
        entry = json.loads(first_line)
    except Exception:
        return None

    payload = entry.get("payload", {}) if isinstance(entry, dict) else {}
    candidates = [
        entry.get("session_id") if isinstance(entry, dict) else None,
        payload.get("id") if isinstance(payload, dict) else None,
        payload.get("session", {}).get("id") if isinstance(payload, dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str):
            match = SESSION_ID_PATTERN.search(candidate)
            if match:
                return match.group(0)
    return None
