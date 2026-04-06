from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .pathing import now_str


@dataclass(frozen=True)
class OpenCodeBindingChange:
    old_id: str
    old_project: str
    new_id: str
    new_project: str


def update_opencode_binding(session, *, session_id: str | None, project_id: str | None) -> None:
    change = binding_change(session, session_id=session_id, project_id=project_id)
    if change is None:
        return

    record_binding_change(session.data, change)
    trigger_transfer_if_needed(session, change)
    mark_session_updated(session.data)
    session._write_back()


def binding_change(session, *, session_id: str | None, project_id: str | None) -> OpenCodeBindingChange | None:
    old_id = str(session.data.get("opencode_session_id") or "").strip()
    old_project = str(session.data.get("opencode_project_id") or "").strip()
    new_id = str(session_id or "").strip()
    new_project = str(project_id or "").strip()
    if not should_record_change(session, session_id=session_id, project_id=project_id):
        return None
    return OpenCodeBindingChange(
        old_id=old_id,
        old_project=old_project,
        new_id=new_id,
        new_project=new_project,
    )


def should_record_change(session, *, session_id: str | None, project_id: str | None) -> bool:
    return any(
        (
            bool(session_id and session.data.get("opencode_session_id") != session_id),
            bool(project_id and session.data.get("opencode_project_id") != project_id),
        )
    )


def record_binding_change(data: dict[str, object], change: OpenCodeBindingChange) -> None:
    if change.new_id:
        data["opencode_session_id"] = change.new_id
    if change.new_project:
        data["opencode_project_id"] = change.new_project
    mark_old_binding(data, change)


def mark_old_binding(data: dict[str, object], change: OpenCodeBindingChange) -> None:
    if change.old_id and change.old_id != change.new_id:
        data["old_opencode_session_id"] = change.old_id
    if change.old_project and change.old_project != change.new_project:
        data["old_opencode_project_id"] = change.old_project
    if change.old_id or change.old_project:
        data["old_updated_at"] = now_str()


def trigger_transfer_if_needed(session, change: OpenCodeBindingChange) -> None:
    if not change.old_id and not change.old_project:
        return
    try:
        from memory.transfer_runtime import maybe_auto_transfer

        maybe_auto_transfer(
            provider="opencode",
            work_dir=Path(session.work_dir),
            session_id=change.old_id or None,
            project_id=change.old_project or None,
        )
    except Exception:
        pass


def mark_session_updated(data: dict[str, object]) -> None:
    data["updated_at"] = now_str()
    if data.get("active") is False:
        data["active"] = True


__all__ = ["update_opencode_binding"]
