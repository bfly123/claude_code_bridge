from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from pane_registry_runtime import upsert_registry
from project_id import compute_ccb_project_id
from provider_sessions.files import safe_write_session

from ..registry_support.pathing import ensure_claude_session_work_dir_fields, infer_work_dir_from_session_file


def remember_claude_session_binding(
    *,
    project_session_file: Path,
    session_path: Path,
    session_info: dict[str, Any],
) -> dict[str, Any] | None:
    if not project_session_file.exists():
        return None
    data = _load_session_payload(project_session_file)
    if not isinstance(data, dict):
        data = {}

    work_dir = str(data.get("work_dir") or "").strip()
    if not work_dir:
        raw_hint = session_info.get("work_dir")
        work_dir = raw_hint.strip() if isinstance(raw_hint, str) else ""
        if work_dir:
            data["work_dir"] = work_dir

    if not work_dir:
        data["work_dir"] = str(infer_work_dir_from_session_file(project_session_file))

    ensure_claude_session_work_dir_fields(data, project_session_file)

    old_path = str(data.get("claude_session_path") or "").strip()
    old_id = str(data.get("claude_session_id") or "").strip()
    session_path_str = str(session_path)
    new_id = str(session_path.stem or "").strip()

    data["claude_session_path"] = session_path_str
    if new_id and data.get("claude_session_id") != new_id:
        data["claude_session_id"] = new_id
    if old_id and old_id != new_id:
        data["old_claude_session_id"] = old_id
    if old_path and old_path != session_path_str:
        data["old_claude_session_path"] = old_path
    if (old_id and old_id != new_id) or (old_path and old_path != session_path_str):
        data["old_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    data["active"] = True

    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    ok, _err = safe_write_session(project_session_file, payload)
    if not ok:
        return None
    return data


def publish_claude_registry(
    *,
    session_info: dict[str, Any],
    terminal: str,
    pane_id: str | None,
    project_session_file: str | None,
) -> None:
    try:
        ccb_session_id = str(session_info.get("ccb_session_id") or os.environ.get("CCB_SESSION_ID") or "").strip()
        if not ccb_session_id:
            return
        wd = session_info.get("work_dir")
        work_dir = Path(wd) if isinstance(wd, str) and wd else Path.cwd()
        ccb_pid = str(session_info.get("ccb_project_id") or "").strip() or compute_ccb_project_id(work_dir)
        upsert_registry(
            {
                "ccb_session_id": ccb_session_id,
                "ccb_project_id": ccb_pid or None,
                "work_dir": str(work_dir),
                "terminal": terminal,
                "providers": {
                    "claude": {
                        "pane_id": pane_id or None,
                        "pane_title_marker": session_info.get("pane_title_marker"),
                        "session_file": project_session_file,
                        "claude_session_id": session_info.get("claude_session_id"),
                        "claude_session_path": session_info.get("claude_session_path"),
                    }
                },
            }
        )
    except Exception:
        pass


def _load_session_payload(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            payload = json.load(handle)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
