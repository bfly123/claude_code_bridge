from __future__ import annotations

from pathlib import Path

from .pathing import now_str


def update_opencode_binding(session, *, session_id: str | None, project_id: str | None) -> None:
    old_id = str(session.data.get("opencode_session_id") or "").strip()
    old_project = str(session.data.get("opencode_project_id") or "").strip()
    updated = False
    if session_id and session.data.get("opencode_session_id") != session_id:
        session.data["opencode_session_id"] = session_id
        updated = True
    if project_id and session.data.get("opencode_project_id") != project_id:
        session.data["opencode_project_id"] = project_id
        updated = True

    if not updated:
        return

    new_id = str(session_id or "").strip()
    new_project = str(project_id or "").strip()
    if old_id and old_id != new_id:
        session.data["old_opencode_session_id"] = old_id
    if old_project and old_project != new_project:
        session.data["old_opencode_project_id"] = old_project
    if old_id or old_project:
        session.data["old_updated_at"] = now_str()
        try:
            from memory.transfer_runtime import maybe_auto_transfer

            maybe_auto_transfer(
                provider="opencode",
                work_dir=Path(session.work_dir),
                session_id=old_id or None,
                project_id=old_project or None,
            )
        except Exception:
            pass

    session.data["updated_at"] = now_str()
    if session.data.get("active") is False:
        session.data["active"] = True
    session._write_back()


__all__ = ["update_opencode_binding"]
