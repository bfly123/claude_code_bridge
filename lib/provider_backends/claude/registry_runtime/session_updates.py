from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from provider_backends.claude.registry_support.logs import read_session_meta
from provider_backends.claude.registry_support.pathing import ensure_claude_session_work_dir_fields
from provider_backends.claude.session import _maybe_auto_extract_old_session
from provider_sessions.files import safe_write_session


def read_log_meta_with_retry(log_path: Path) -> tuple[Optional[str], Optional[str], Optional[bool]]:
    for attempt in range(2):
        cwd, sid, is_sidechain = read_session_meta(log_path)
        if cwd or sid or is_sidechain is True:
            return cwd, sid, is_sidechain
        if attempt == 0:
            time.sleep(0.2)
    return None, None, None


def update_session_file_direct(session_file: Path, log_path: Path, session_id: str) -> None:
    if not session_file.exists():
        return
    try:
        payload = json.loads(session_file.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    old_path = str(payload.get("claude_session_path") or "").strip()
    old_id = str(payload.get("claude_session_id") or "").strip()
    work_dir_path = ensure_claude_session_work_dir_fields(payload, session_file)
    new_path = str(log_path)
    new_id = str(session_id or "").strip()
    if old_id and old_id != new_id:
        payload["old_claude_session_id"] = old_id
    if old_path and old_path != new_path:
        payload["old_claude_session_path"] = old_path
    if (old_id and old_id != new_id) or (old_path and old_path != new_path):
        payload["old_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    payload["claude_session_path"] = str(log_path)
    payload["claude_session_id"] = session_id
    payload["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if payload.get("active") is False:
        payload["active"] = True
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    ok, _err = safe_write_session(session_file, content)
    if not ok:
        return
    if old_path and old_path != new_path and work_dir_path:
        _maybe_auto_extract_old_session(old_path, work_dir_path)
