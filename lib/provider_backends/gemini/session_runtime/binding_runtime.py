from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from project.identity import compute_ccb_project_id

from .pathing import now_str


@dataclass(frozen=True)
class GeminiBindingChange:
    old_path: str
    old_id: str
    new_path: str
    new_id: str
    project_hash: str
    ccb_project_id: str


def update_gemini_binding(session, *, session_path: Path | None, session_id: str | None) -> None:
    change = binding_change(session, session_path=session_path, session_id=session_id)
    if change is None:
        return

    record_binding_change(session.data, change)
    trigger_transfer_if_needed(session, change)
    mark_session_updated(session.data)
    session._write_back()


def binding_change(session, *, session_path: Path | None, session_id: str | None) -> GeminiBindingChange | None:
    old_path = str(session.data.get("gemini_session_path") or "").strip()
    old_id = str(session.data.get("gemini_session_id") or "").strip()
    new_path = normalized_session_path(session_path)
    new_id = normalized_session_id(session_id, session_path=session_path)
    project_hash = session_project_hash(new_path)
    ccb_project_id = ensured_project_id(session)
    if not should_record_change(
        session,
        new_path=new_path,
        session_id=session_id,
        project_hash=project_hash,
        ccb_project_id=ccb_project_id,
    ):
        return None
    return GeminiBindingChange(
        old_path=old_path,
        old_id=old_id,
        new_path=new_path,
        new_id=new_id,
        project_hash=project_hash,
        ccb_project_id=ccb_project_id,
    )


def normalized_session_path(session_path: Path | None) -> str:
    if session_path is None:
        return ""
    try:
        return str(Path(session_path).expanduser())
    except Exception:
        return str(session_path)


def normalized_session_id(session_id: str | None, *, session_path: Path | None) -> str:
    new_id = str(session_id or "").strip()
    if new_id or session_path is None:
        return new_id
    try:
        return Path(session_path).stem
    except Exception:
        return ""


def session_project_hash(session_path: str) -> str:
    if not session_path:
        return ""
    try:
        return Path(session_path).parent.parent.name
    except Exception:
        return ""


def ensured_project_id(session) -> str:
    current = str(session.data.get("ccb_project_id") or "").strip()
    if current:
        return current
    try:
        return compute_ccb_project_id(Path(session.work_dir))
    except Exception:
        return ""


def should_record_change(
    session,
    *,
    new_path: str,
    session_id: str | None,
    project_hash: str,
    ccb_project_id: str,
) -> bool:
    return any(
        (
            bool(new_path and session.data.get("gemini_session_path") != new_path),
            bool(project_hash and session.data.get("gemini_project_hash") != project_hash),
            bool(session_id and session.data.get("gemini_session_id") != session_id),
            bool(ccb_project_id and session.data.get("ccb_project_id") != ccb_project_id),
        )
    )


def record_binding_change(data: dict[str, object], change: GeminiBindingChange) -> None:
    if change.new_path:
        data["gemini_session_path"] = change.new_path
    if change.project_hash:
        data["gemini_project_hash"] = change.project_hash
    if change.new_id:
        data["gemini_session_id"] = change.new_id
    if change.ccb_project_id:
        data["ccb_project_id"] = change.ccb_project_id
    mark_old_binding(data, change)


def mark_old_binding(data: dict[str, object], change: GeminiBindingChange) -> None:
    if change.old_id and change.old_id != change.new_id:
        data["old_gemini_session_id"] = change.old_id
    if change.old_path and (change.old_path != change.new_path or (change.old_id and change.old_id != change.new_id)):
        data["old_gemini_session_path"] = change.old_path
    if change.old_path or change.old_id:
        data["old_updated_at"] = now_str()


def trigger_transfer_if_needed(session, change: GeminiBindingChange) -> None:
    if not change.old_path and not change.old_id:
        return
    try:
        from memory.transfer_runtime import maybe_auto_transfer

        maybe_auto_transfer(
            provider="gemini",
            work_dir=Path(session.work_dir),
            session_path=expanded_old_path(change.old_path),
            session_id=change.old_id or None,
        )
    except Exception:
        pass


def expanded_old_path(old_path: str) -> Path | None:
    if not old_path:
        return None
    try:
        return Path(old_path).expanduser()
    except Exception:
        return None


def mark_session_updated(data: dict[str, object]) -> None:
    data["updated_at"] = now_str()
    if data.get("active") is False:
        data["active"] = True


__all__ = ["update_gemini_binding"]
