from __future__ import annotations

import os
from pathlib import Path

from ..debug import debug_log_reader
from ..project_hash import project_root_marker
from .project_scope import adopt_project_hash_from_session, session_belongs_to_current_project


def scan_latest_session_any_project(reader) -> Path | None:
    if not reader.root.exists():
        return None
    try:
        sessions = sorted(
            _iter_session_files(reader.root.glob("*/chats/session-*.json")),
            key=lambda path: path.stat().st_mtime,
        )
    except OSError:
        return None
    return sessions[-1] if sessions else None


def scan_latest_session(reader) -> Path | None:
    best: Path | None = None
    best_mtime = 0.0
    winning_hash = reader._project_hash
    for project_hash in _project_scan_order(reader):
        latest = _latest_project_session(reader, project_hash)
        if latest is None:
            continue
        path, mtime = latest
        if mtime > best_mtime:
            best_mtime = mtime
            best = path
            winning_hash = project_hash

    if best is None:
        return None
    if winning_hash != reader._project_hash:
        reader._project_hash = winning_hash
        debug_log_reader(f"Adopted project hash: {winning_hash}")
    return best


def latest_session(reader) -> Path | None:
    preferred = reader._preferred_session
    if preferred and not session_belongs_to_current_project(reader, preferred):
        reader._preferred_session = None
        preferred = None

    scanned = scan_latest_session(reader)
    preferred_or_scanned = _select_preferred_session(reader, preferred=preferred, scanned=scanned)
    if preferred_or_scanned is not None:
        return preferred_or_scanned

    if os.environ.get("GEMINI_ALLOW_ANY_PROJECT_SCAN") not in ("1", "true", "yes"):
        return None
    any_latest = scan_latest_session_any_project(reader)
    if any_latest is None:
        return None
    reader._preferred_session = any_latest
    adopt_project_hash_from_session(reader, any_latest)
    debug_log_reader(f"Fallback scan (any project) found: {any_latest}")
    return any_latest


def set_preferred_session(reader, session_path: Path | None) -> None:
    if not session_path or not session_belongs_to_current_project(reader, session_path):
        return
    reader._preferred_session = session_path
    adopt_project_hash_from_session(reader, session_path)


def _select_preferred_session(reader, *, preferred: Path | None, scanned: Path | None) -> Path | None:
    if preferred and preferred.exists():
        if scanned and scanned.exists():
            try:
                pref_mtime = preferred.stat().st_mtime
                scan_mtime = scanned.stat().st_mtime
            except OSError:
                pref_mtime = 0.0
                scan_mtime = 0.0
            if scan_mtime > pref_mtime:
                debug_log_reader(f"Scanned session newer: {scanned} ({scan_mtime}) > {preferred} ({pref_mtime})")
                reader._preferred_session = scanned
                return scanned
        debug_log_reader(f"Using preferred session: {preferred}")
        return preferred

    if scanned is not None:
        reader._preferred_session = scanned
        debug_log_reader(f"Scan found: {scanned}")
        return scanned
    return None


def _project_scan_order(reader) -> list[str]:
    scan_order = [reader._project_hash]
    for project_hash in sorted(reader._all_known_hashes - {reader._project_hash}):
        scan_order.append(project_hash)
    unique_order: list[str] = []
    seen: set[str] = set()
    for project_hash in scan_order:
        if project_hash in seen:
            continue
        seen.add(project_hash)
        unique_order.append(project_hash)
    return unique_order


def _latest_project_session(reader, project_hash: str) -> tuple[Path, float] | None:
    chats = reader.root / project_hash / "chats"
    if not chats.is_dir():
        return None
    marker = project_root_marker(chats.parent)
    if marker and marker != reader._work_dir_norm:
        return None
    best: tuple[Path, float] | None = None
    try:
        for path in _iter_session_files(chats.iterdir()):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if best is None or mtime > best[1]:
                best = (path, mtime)
    except OSError:
        return None
    return best


def _iter_session_files(paths) -> list[Path]:
    return [
        path
        for path in paths
        if path.is_file() and not path.name.startswith(".") and path.suffix == ".json" and path.name.startswith("session-")
    ]


__all__ = [
    "latest_session",
    "scan_latest_session",
    "scan_latest_session_any_project",
    "set_preferred_session",
]
