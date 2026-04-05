from __future__ import annotations

from pathlib import Path

from .pathing import now_str
from ..start_cmd import persist_resume_start_cmd_fields


def update_codex_log_binding(session, *, log_path: str | None, session_id: str | None) -> None:
    old_path = str(session.data.get("codex_session_path") or "").strip()
    old_id = str(session.data.get("codex_session_id") or "").strip()
    old_start_cmd = str(session.data.get("start_cmd") or "").strip()
    old_codex_start_cmd = str(session.data.get("codex_start_cmd") or "").strip()

    updated = False
    log_path_str = str(log_path or "").strip()
    if log_path_str and session.data.get("codex_session_path") != log_path_str:
        session.data["codex_session_path"] = log_path_str
        updated = True
    if session_id:
        if session.data.get("codex_session_id") != session_id:
            session.data["codex_session_id"] = session_id
            updated = True
        resume_start_cmd = persist_resume_start_cmd_fields(session.data, session_id)
        if resume_start_cmd is not None and (
            old_start_cmd != resume_start_cmd or old_codex_start_cmd != resume_start_cmd
        ):
            updated = True

    if not updated:
        return

    new_id = str(session_id or "").strip()
    if not new_id and log_path_str:
        try:
            new_id = Path(log_path_str).stem
        except Exception:
            new_id = ""
    if old_id and old_id != new_id:
        session.data["old_codex_session_id"] = old_id
    if old_path and (old_path != log_path_str or (old_id and old_id != new_id)):
        session.data["old_codex_session_path"] = old_path
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
                provider="codex",
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


__all__ = ["update_codex_log_binding"]
