from __future__ import annotations

from pathlib import Path

from project_id import compute_ccb_project_id

from .pathing import now_str


def update_gemini_binding(session, *, session_path: Path | None, session_id: str | None) -> None:
    old_path = str(session.data.get("gemini_session_path") or "").strip()
    old_id = str(session.data.get("gemini_session_id") or "").strip()
    updated = False
    session_path_str = ""
    if session_path:
        try:
            session_path_str = str(Path(session_path).expanduser())
        except Exception:
            session_path_str = str(session_path)
        if session_path_str and session.data.get("gemini_session_path") != session_path_str:
            session.data["gemini_session_path"] = session_path_str
            updated = True
        try:
            project_hash = Path(session_path_str).parent.parent.name
        except Exception:
            project_hash = ""
        if project_hash and session.data.get("gemini_project_hash") != project_hash:
            session.data["gemini_project_hash"] = project_hash
            updated = True

    if session_id and session.data.get("gemini_session_id") != session_id:
        session.data["gemini_session_id"] = session_id
        updated = True

    if not str(session.data.get("ccb_project_id") or "").strip():
        try:
            session.data["ccb_project_id"] = compute_ccb_project_id(Path(session.work_dir))
            updated = True
        except Exception:
            pass

    if not updated:
        return

    new_id = str(session_id or "").strip()
    if not new_id and session_path:
        try:
            new_id = Path(session_path).stem
        except Exception:
            new_id = ""
    session_path_text = str(session_path) if session_path else ""
    if old_id and old_id != new_id:
        session.data["old_gemini_session_id"] = old_id
    if old_path and (old_path != session_path_text or (old_id and old_id != new_id)):
        session.data["old_gemini_session_path"] = old_path
    if old_path or old_id:
        session.data["old_updated_at"] = now_str()
        try:
            from memory.transfer_runtime import maybe_auto_transfer

            old_path_obj = None
            if old_path:
                try:
                    old_path_obj = Path(old_path).expanduser()
                except Exception:
                    old_path_obj = None
            maybe_auto_transfer(
                provider="gemini",
                work_dir=Path(session.work_dir),
                session_path=old_path_obj,
                session_id=old_id or None,
            )
        except Exception:
            pass

    session.data["updated_at"] = now_str()
    if session.data.get("active") is False:
        session.data["active"] = True
    session._write_back()


__all__ = ["update_gemini_binding"]
