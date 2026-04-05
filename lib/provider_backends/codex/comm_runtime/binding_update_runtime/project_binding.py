from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_id import compute_ccb_project_id

from ..binding import extract_session_id
from ...start_cmd import persist_resume_start_cmd_fields
from .history_transfer import apply_old_binding_metadata
from .persistence import write_project_session


@dataclass(frozen=True)
class CodexBindingState:
    path_str: str
    session_id: str
    resume_cmd: str | None
    start_cmd: str | None
    ccb_project_id: str


def update_project_session_binding(
    *,
    project_file: Path,
    log_path: Path,
    session_info: dict[str, Any],
    debug_enabled: bool = False,
) -> CodexBindingState | None:
    if not project_file.exists():
        return None
    try:
        with project_file.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None

    ccb_project_id = compute_project_id(session_info)
    path_str = str(log_path)
    session_id = str(extract_session_id(log_path) or "").strip()
    resume_cmd = None

    if binding_is_stale(data, log_path, debug_enabled=debug_enabled):
        return None

    old_path = str(data.get("codex_session_path") or "").strip()
    old_id = str(data.get("codex_session_id") or "").strip()
    old_start_cmd = str(data.get("start_cmd") or "").strip()
    old_codex_start_cmd = str(data.get("codex_start_cmd") or "").strip()
    updated = False
    binding_changed = False

    if data.get("codex_session_path") != path_str:
        data["codex_session_path"] = path_str
        updated = True
        binding_changed = True
    if session_id and data.get("codex_session_id") != session_id:
        data["codex_session_id"] = session_id
        updated = True
        binding_changed = True
    if ccb_project_id and data.get("ccb_project_id") != ccb_project_id:
        data["ccb_project_id"] = ccb_project_id
        updated = True
    if session_id:
        resume_cmd = persist_resume_start_cmd_fields(data, session_id)
        if resume_cmd is not None and (old_start_cmd != resume_cmd or old_codex_start_cmd != resume_cmd):
            updated = True
    elif str(data.get("codex_start_cmd") or "").startswith("codex resume "):
        pass
    if data.get("active") is False:
        data["active"] = True
        updated = True

    if updated:
        apply_old_binding_metadata(
            data,
            old_path=old_path,
            old_id=old_id,
            new_path=path_str,
            new_id=session_id,
            binding_changed=binding_changed,
            session_info=session_info,
        )
        write_project_session(project_file, data)

    return CodexBindingState(
        path_str=path_str,
        session_id=session_id,
        resume_cmd=resume_cmd,
        start_cmd=str(data.get("start_cmd") or "").strip() or None,
        ccb_project_id=ccb_project_id,
    )


def compute_project_id(session_info: dict[str, Any]) -> str:
    try:
        wd_hint = session_info.get("work_dir")
        if isinstance(wd_hint, str) and wd_hint.strip():
            return compute_ccb_project_id(Path(wd_hint.strip()))
    except Exception:
        return ""
    return ""


def binding_is_stale(data: dict[str, Any], log_path: Path, *, debug_enabled: bool) -> bool:
    started_at = data.get("started_at")
    if not started_at or data.get("codex_session_path") or data.get("codex_session_id"):
        return False
    try:
        started_ts = time.mktime(time.strptime(started_at, "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return False
    try:
        log_mtime = log_path.stat().st_mtime
    except OSError:
        return False
    if log_mtime >= started_ts:
        return False
    if debug_enabled:
        print(
            f"[DEBUG] Skip binding log older than session start: {log_path}",
            file=sys.stderr,
        )
    return True


__all__ = [
    "CodexBindingState",
    "binding_is_stale",
    "compute_project_id",
    "update_project_session_binding",
]
