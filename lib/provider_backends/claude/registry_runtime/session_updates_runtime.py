from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from provider_backends.claude.registry_support.logs import read_session_meta
from provider_backends.claude.registry_support.pathing import ensure_claude_session_work_dir_fields
from provider_backends.claude.session_runtime import maybe_auto_extract_old_session
from provider_sessions.files import safe_write_session


def read_log_meta_with_retry(log_path: Path) -> tuple[Optional[str], Optional[str], Optional[bool]]:
    for attempt in range(2):
        work_dir, session_id, is_sidechain = read_session_meta(log_path)
        if meta_found(work_dir, session_id, is_sidechain):
            return work_dir, session_id, is_sidechain
        if attempt == 0:
            time.sleep(0.2)
    return None, None, None


def meta_found(work_dir: Optional[str], session_id: Optional[str], is_sidechain: Optional[bool]) -> bool:
    return bool(work_dir or session_id or is_sidechain is True)


def update_session_file_direct(session_file: Path, log_path: Path, session_id: str) -> None:
    if not session_file.exists():
        return

    payload = load_session_payload(session_file)
    old_path, old_id = current_binding(payload)
    work_dir_path = ensure_claude_session_work_dir_fields(payload, session_file)
    apply_binding_update(payload, log_path=log_path, session_id=session_id, old_path=old_path, old_id=old_id)
    if not write_session_payload(session_file, payload):
        return
    maybe_extract_replaced_session(old_path=old_path, new_path=str(log_path), work_dir_path=work_dir_path)


def load_session_payload(session_file: Path) -> dict[str, object]:
    try:
        payload = json.loads(session_file.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def current_binding(payload: dict[str, object]) -> tuple[str, str]:
    return (
        str(payload.get("claude_session_path") or "").strip(),
        str(payload.get("claude_session_id") or "").strip(),
    )


def apply_binding_update(
    payload: dict[str, object],
    *,
    log_path: Path,
    session_id: str,
    old_path: str,
    old_id: str,
) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    new_path = str(log_path)
    new_id = str(session_id or "").strip()

    mark_old_binding(payload, old_path=old_path, old_id=old_id, new_path=new_path, new_id=new_id, timestamp=timestamp)
    payload["claude_session_path"] = new_path
    payload["claude_session_id"] = session_id
    payload["updated_at"] = timestamp
    if payload.get("active") is False:
        payload["active"] = True


def mark_old_binding(
    payload: dict[str, object],
    *,
    old_path: str,
    old_id: str,
    new_path: str,
    new_id: str,
    timestamp: str,
) -> None:
    path_changed = bool(old_path and old_path != new_path)
    id_changed = bool(old_id and old_id != new_id)
    if id_changed:
        payload["old_claude_session_id"] = old_id
    if path_changed:
        payload["old_claude_session_path"] = old_path
    if path_changed or id_changed:
        payload["old_updated_at"] = timestamp


def write_session_payload(session_file: Path, payload: dict[str, object]) -> bool:
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    ok, _err = safe_write_session(session_file, content)
    return ok


def maybe_extract_replaced_session(*, old_path: str, new_path: str, work_dir_path: Path | None) -> None:
    if not old_path or old_path == new_path or work_dir_path is None:
        return
    maybe_auto_extract_old_session(old_path, work_dir_path)


__all__ = ["read_log_meta_with_retry", "update_session_file_direct"]
