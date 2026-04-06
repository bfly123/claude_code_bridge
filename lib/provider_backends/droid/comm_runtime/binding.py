from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

from pane_registry_runtime import upsert_registry
from project.identity import compute_ccb_project_id
from provider_sessions.files import safe_write_session


def remember_droid_session_binding(
    *,
    project_session_file: Path,
    session_path: Path,
    session_id_loader: Callable[[Path], tuple[Optional[str], Optional[str]]],
) -> dict[str, Any] | None:
    try:
        with project_session_file.open("r", encoding="utf-8", errors="replace") as handle:
            data = json.load(handle)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    updated = False
    old_path = str(data.get("droid_session_path") or "").strip()
    old_id = str(data.get("droid_session_id") or "").strip()
    session_path_str = str(session_path)
    binding_changed = False
    if data.get("droid_session_path") != session_path_str:
        data["droid_session_path"] = session_path_str
        updated = True
        binding_changed = True

    _cwd, session_id = session_id_loader(session_path)
    if session_id and data.get("droid_session_id") != session_id:
        data["droid_session_id"] = session_id
        updated = True
        binding_changed = True

    if not (data.get("ccb_project_id") or "").strip():
        try:
            wd = data.get("work_dir")
            if isinstance(wd, str) and wd.strip():
                data["ccb_project_id"] = compute_ccb_project_id(Path(wd.strip()))
                updated = True
        except Exception:
            pass

    if not updated:
        return data

    new_id = str(session_id or "").strip()
    if not new_id:
        try:
            new_id = Path(session_path_str).stem
        except Exception:
            new_id = ""
    if old_id and old_id != new_id:
        data["old_droid_session_id"] = old_id
    if old_path and (old_path != session_path_str or (old_id and old_id != new_id)):
        data["old_droid_session_path"] = old_path
    if (old_path or old_id) and binding_changed:
        data["old_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            from memory.transfer_runtime import maybe_auto_transfer

            old_path_obj = None
            if old_path:
                try:
                    old_path_obj = Path(old_path).expanduser()
                except Exception:
                    old_path_obj = None
            wd = data.get("work_dir")
            work_dir = Path(wd) if isinstance(wd, str) and wd else Path.cwd()
            maybe_auto_transfer(
                provider="droid",
                work_dir=work_dir,
                session_path=old_path_obj,
                session_id=old_id or None,
            )
        except Exception:
            pass

    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    safe_write_session(project_session_file, payload)
    return data


def publish_droid_registry(
    *,
    session_info: dict[str, Any],
    ccb_session_id: str,
    terminal: str,
    pane_id: str | None,
    project_session_file: str | None,
) -> None:
    try:
        wd = session_info.get("work_dir")
        ccb_pid = compute_ccb_project_id(Path(wd)) if isinstance(wd, str) and wd else ""
        upsert_registry(
            {
                "ccb_session_id": ccb_session_id,
                "ccb_project_id": ccb_pid or None,
                "work_dir": wd,
                "terminal": terminal,
                "providers": {
                    "droid": {
                        "pane_id": pane_id or None,
                        "pane_title_marker": session_info.get("pane_title_marker"),
                        "session_file": project_session_file,
                        "droid_session_id": session_info.get("droid_session_id"),
                        "droid_session_path": session_info.get("droid_session_path"),
                    }
                },
            }
        )
    except Exception:
        pass
