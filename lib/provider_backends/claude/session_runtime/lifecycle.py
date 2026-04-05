from __future__ import annotations

import json
from pathlib import Path

from provider_backends.pane_log_support.lifecycle import ensure_pane as _ensure_pane_impl
from provider_sessions.files import safe_write_session

from .auto_transfer import maybe_auto_extract_old_session
from .pathing import ensure_work_dir_fields, now_str


def attach_pane_log(session, backend: object, pane_id: str) -> None:
    ensure = getattr(backend, "ensure_pane_log", None)
    if callable(ensure):
        try:
            ensure(str(pane_id))
        except Exception:
            pass


def ensure_pane(session) -> tuple[bool, str]:
    return _ensure_pane_impl(session, now_str_fn=now_str, attach_pane_log_fn=attach_pane_log)


def update_claude_binding(session, *, session_path: Path | None, session_id: str | None) -> None:
    old_path = str(session.data.get("claude_session_path") or "").strip()
    old_id = str(session.data.get("claude_session_id") or "").strip()
    updated = False
    session_path_str = ""
    if session_path:
        try:
            session_path_str = str(Path(session_path).expanduser())
        except Exception:
            session_path_str = str(session_path)
        if session_path_str and session.data.get("claude_session_path") != session_path_str:
            session.data["claude_session_path"] = session_path_str
            updated = True

    if session_id and session.data.get("claude_session_id") != session_id:
        session.data["claude_session_id"] = session_id
        updated = True

    if not updated:
        return

    new_id = str(session_id or "").strip()
    if not new_id and session_path_str:
        try:
            new_id = Path(session_path_str).stem
        except Exception:
            new_id = ""
    if old_id and old_id != new_id:
        session.data["old_claude_session_id"] = old_id
    if old_path and (old_path != session_path_str or (old_id and old_id != new_id)):
        session.data["old_claude_session_path"] = old_path
    if old_path or old_id:
        session.data["old_updated_at"] = now_str()
    session.data["updated_at"] = now_str()
    if session.data.get("active") is False:
        session.data["active"] = True
    session._write_back()

    changed = False
    if session_path_str:
        changed = old_path != session_path_str
    elif new_id:
        changed = new_id != old_id
    if changed and old_path:
        maybe_auto_extract_old_session(old_path, Path(session.work_dir))


def write_back(session) -> None:
    ensure_work_dir_fields(session.data, session_file=session.session_file)
    payload = json.dumps(session.data, ensure_ascii=False, indent=2) + "\n"
    ok, _err = safe_write_session(session.session_file, payload)
    if not ok:
        return


__all__ = ["attach_pane_log", "ensure_pane", "update_claude_binding", "write_back"]
