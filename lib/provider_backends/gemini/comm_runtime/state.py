from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .project_hash import get_project_hash, normalize_project_path, project_hash_candidates


def initialize_reader(reader, *, root: Path, work_dir: Path | None) -> None:
    reader.root = Path(root).expanduser()
    reader.work_dir = work_dir or Path.cwd()
    reader._work_dir_norm = normalize_project_path(reader.work_dir)
    forced_hash = os.environ.get("GEMINI_PROJECT_HASH", "").strip()
    if forced_hash:
        reader._project_hash = forced_hash
        reader._all_known_hashes = {forced_hash}
    else:
        reader._project_hash = get_project_hash(reader.work_dir, root=reader.root)
        reader._all_known_hashes = set(project_hash_candidates(reader.work_dir, root=reader.root))
        reader._all_known_hashes.add(reader._project_hash)
    reader._preferred_session = None
    try:
        poll = float(os.environ.get("GEMINI_POLL_INTERVAL", "0.05"))
    except Exception:
        poll = 0.05
    reader._poll_interval = min(0.5, max(0.02, poll))
    try:
        force = float(os.environ.get("GEMINI_FORCE_READ_INTERVAL", "1.0"))
    except Exception:
        force = 1.0
    reader._force_read_interval = min(5.0, max(0.2, force))


def state_payload(
    *,
    session: Path | None,
    msg_count: int,
    mtime: float,
    mtime_ns: int,
    size: int,
    last_gemini_id: str | None,
    last_gemini_hash: str | None,
    last_tool_call_count: int = 0,
    last_thought_count: int = 0,
) -> dict[str, Any]:
    return {
        "session_path": session,
        "msg_count": msg_count,
        "mtime": mtime,
        "mtime_ns": mtime_ns,
        "size": size,
        "last_gemini_id": last_gemini_id,
        "last_gemini_hash": last_gemini_hash,
        "last_tool_call_count": int(last_tool_call_count or 0),
        "last_thought_count": int(last_thought_count or 0),
    }


__all__ = ["initialize_reader", "state_payload"]
