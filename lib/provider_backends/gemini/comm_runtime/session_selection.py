from __future__ import annotations

import os
from pathlib import Path

from .debug import debug_log_reader
from .project_hash import normalize_project_path, project_root_marker


def session_belongs_to_current_project(reader, session_path: Path) -> bool:
    try:
        candidate = Path(session_path).expanduser()
    except Exception:
        return False
    if not candidate.exists():
        return False
    try:
        resolved_candidate = candidate.resolve()
    except Exception:
        resolved_candidate = candidate.absolute()
    if resolved_candidate.parent.name != "chats":
        return False
    project_dir = resolved_candidate.parent.parent
    project_hash = (project_dir.name or "").strip()
    if not project_hash:
        return False

    try:
        resolved_root = reader.root.resolve()
    except Exception:
        resolved_root = reader.root.absolute()
    if project_dir.parent != resolved_root:
        return False
    marker = project_root_marker(project_dir)
    if marker and marker != reader._work_dir_norm:
        return False
    return project_hash == reader._project_hash or project_hash in reader._all_known_hashes


def scan_latest_session_any_project(reader) -> Path | None:
    if not reader.root.exists():
        return None
    try:
        sessions = sorted(
            (path for path in reader.root.glob("*/chats/session-*.json") if path.is_file() and not path.name.startswith(".")),
            key=lambda path: path.stat().st_mtime,
        )
    except OSError:
        return None
    return sessions[-1] if sessions else None


def scan_latest_session(reader) -> Path | None:
    scan_order = [reader._project_hash]
    for project_hash in sorted(reader._all_known_hashes - {reader._project_hash}):
        scan_order.append(project_hash)

    seen: set[str] = set()
    unique_order: list[str] = []
    for project_hash in scan_order:
        if project_hash not in seen:
            seen.add(project_hash)
            unique_order.append(project_hash)

    best: Path | None = None
    best_mtime = 0.0
    winning_hash = reader._project_hash
    for project_hash in unique_order:
        chats = reader.root / project_hash / "chats"
        if not chats.is_dir():
            continue
        marker = project_root_marker(chats.parent)
        if marker and marker != reader._work_dir_norm:
            continue
        try:
            for path in chats.iterdir():
                if not path.is_file() or path.name.startswith("."):
                    continue
                if not (path.suffix == ".json" and path.name.startswith("session-")):
                    continue
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                if mtime > best_mtime:
                    best_mtime = mtime
                    best = path
                    winning_hash = project_hash
        except OSError:
            continue

    if best:
        if winning_hash != reader._project_hash:
            reader._project_hash = winning_hash
            debug_log_reader(f"Adopted project hash: {winning_hash}")
        return best

    return None


def latest_session(reader) -> Path | None:
    preferred = reader._preferred_session
    if preferred and not session_belongs_to_current_project(reader, preferred):
        reader._preferred_session = None
        preferred = None
    scanned = scan_latest_session(reader)

    if preferred and preferred.exists():
        if scanned and scanned.exists():
            try:
                pref_mtime = preferred.stat().st_mtime
                scan_mtime = scanned.stat().st_mtime
                if scan_mtime > pref_mtime:
                    debug_log_reader(
                        f"Scanned session newer: {scanned} ({scan_mtime}) > {preferred} ({pref_mtime})"
                    )
                    reader._preferred_session = scanned
                    return scanned
            except OSError:
                pass
        debug_log_reader(f"Using preferred session: {preferred}")
        return preferred

    if scanned:
        reader._preferred_session = scanned
        debug_log_reader(f"Scan found: {scanned}")
        return scanned
    if os.environ.get("GEMINI_ALLOW_ANY_PROJECT_SCAN") in ("1", "true", "yes"):
        any_latest = scan_latest_session_any_project(reader)
        if any_latest:
            reader._preferred_session = any_latest
            try:
                project_hash = any_latest.parent.parent.name
                if project_hash:
                    reader._project_hash = project_hash
            except Exception:
                pass
            debug_log_reader(f"Fallback scan (any project) found: {any_latest}")
            return any_latest
    return None


def set_preferred_session(reader, session_path: Path | None) -> None:
    if not session_path:
        return
    try:
        candidate = session_path if isinstance(session_path, Path) else Path(str(session_path)).expanduser()
    except Exception:
        return
    if candidate.exists() and session_belongs_to_current_project(reader, candidate):
        reader._preferred_session = candidate
        try:
            project_hash = candidate.resolve().parent.parent.name
        except Exception:
            project_hash = candidate.parent.parent.name if candidate.parent.name == "chats" else ""
        if project_hash:
            reader._project_hash = project_hash
            reader._all_known_hashes.add(project_hash)


__all__ = [
    "latest_session",
    "scan_latest_session",
    "scan_latest_session_any_project",
    "session_belongs_to_current_project",
    "set_preferred_session",
]
