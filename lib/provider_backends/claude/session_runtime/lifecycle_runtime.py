from __future__ import annotations

import json
from pathlib import Path

from provider_backends.pane_log_support.lifecycle import ensure_pane as _ensure_pane_impl
from provider_sessions.files import safe_write_session

from .auto_transfer import maybe_auto_extract_old_session
from .pathing import ensure_work_dir_fields, now_str


def attach_pane_log(session, backend: object, pane_id: str) -> None:
    ensure = getattr(backend, "ensure_pane_log", None)
    if not callable(ensure):
        return
    try:
        ensure(str(pane_id))
    except Exception:
        pass


def ensure_pane(session) -> tuple[bool, str]:
    return _ensure_pane_impl(session, now_str_fn=now_str, attach_pane_log_fn=attach_pane_log)


def update_claude_binding(session, *, session_path: Path | None, session_id: str | None) -> None:
    change = binding_change(session, session_path=session_path, session_id=session_id)
    if change is None:
        return

    record_binding_change(session, change)
    session._write_back()
    maybe_extract_previous_binding(session, change)


def binding_change(session, *, session_path: Path | None, session_id: str | None) -> dict[str, object] | None:
    old_path = str(session.data.get("claude_session_path") or "").strip()
    old_id = str(session.data.get("claude_session_id") or "").strip()
    new_path = normalized_session_path(session_path)
    new_id = normalized_session_id(session_id, session_path_str=new_path)
    path_changed = bool(new_path and session.data.get("claude_session_path") != new_path)
    id_changed = bool(session_id and session.data.get("claude_session_id") != session_id)
    if not path_changed and not id_changed:
        return None
    return {
        "old_path": old_path,
        "old_id": old_id,
        "new_path": new_path,
        "new_id": new_id,
        "path_changed": path_changed,
        "id_changed": id_changed,
    }


def normalized_session_path(session_path: Path | None) -> str:
    if session_path is None:
        return ""
    try:
        return str(Path(session_path).expanduser())
    except Exception:
        return str(session_path)


def normalized_session_id(session_id: str | None, *, session_path_str: str) -> str:
    new_id = str(session_id or "").strip()
    if new_id or not session_path_str:
        return new_id
    try:
        return Path(session_path_str).stem
    except Exception:
        return ""


def record_binding_change(session, change: dict[str, object]) -> None:
    old_path = str(change["old_path"])
    old_id = str(change["old_id"])
    new_path = str(change["new_path"])
    new_id = str(change["new_id"])

    if new_path:
        session.data["claude_session_path"] = new_path
    if new_id:
        session.data["claude_session_id"] = new_id
    mark_old_binding(session.data, old_path=old_path, old_id=old_id, new_path=new_path, new_id=new_id)
    session.data["updated_at"] = now_str()
    if session.data.get("active") is False:
        session.data["active"] = True


def mark_old_binding(data: dict[str, object], *, old_path: str, old_id: str, new_path: str, new_id: str) -> None:
    if old_id and old_id != new_id:
        data["old_claude_session_id"] = old_id
    if old_path and (old_path != new_path or (old_id and old_id != new_id)):
        data["old_claude_session_path"] = old_path
    if old_path or old_id:
        data["old_updated_at"] = now_str()


def maybe_extract_previous_binding(session, change: dict[str, object]) -> None:
    old_path = str(change["old_path"])
    new_path = str(change["new_path"])
    new_id = str(change["new_id"])
    old_id = str(change["old_id"])
    changed = old_path != new_path if new_path else new_id != old_id
    if changed and old_path:
        maybe_auto_extract_old_session(old_path, Path(session.work_dir))


def write_back(session) -> None:
    ensure_work_dir_fields(session.data, session_file=session.session_file)
    payload = json.dumps(session.data, ensure_ascii=False, indent=2) + "\n"
    ok, _err = safe_write_session(session.session_file, payload)
    if not ok:
        return


__all__ = ["attach_pane_log", "ensure_pane", "update_claude_binding", "write_back"]
