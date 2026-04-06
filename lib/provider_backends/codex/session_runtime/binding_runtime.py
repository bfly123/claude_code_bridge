from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..start_cmd import persist_resume_start_cmd_fields
from .pathing import now_str


@dataclass(frozen=True)
class CurrentBindingState:
    path: str
    session_id: str
    start_cmd: str
    codex_start_cmd: str


@dataclass(frozen=True)
class RequestedBinding:
    path: str
    session_id: str


@dataclass(frozen=True)
class BindingChange:
    old_path: str
    old_id: str
    new_path: str
    new_id: str


def update_codex_log_binding(session, *, log_path: str | None, session_id: str | None) -> None:
    change = binding_change(session, log_path=log_path, session_id=session_id)
    if change is None:
        return

    record_binding_change(session, change)
    trigger_transfer_if_needed(session, change)
    session.data["updated_at"] = now_str()
    mark_active(session.data)
    session._write_back()


def binding_change(session, *, log_path: str | None, session_id: str | None) -> BindingChange | None:
    current = current_binding_state(session)
    requested = requested_binding(log_path=log_path, session_id=session_id)
    resume_start_cmd = persist_resume_start_cmd_fields(session.data, session_id) if session_id else None
    if not should_record_binding_change(session, current, requested, session_id=session_id, resume_start_cmd=resume_start_cmd):
        return None
    return BindingChange(
        old_path=current.path,
        old_id=current.session_id,
        new_path=requested.path,
        new_id=requested.session_id,
    )


def current_binding_state(session) -> CurrentBindingState:
    return CurrentBindingState(
        path=str(session.data.get("codex_session_path") or "").strip(),
        session_id=str(session.data.get("codex_session_id") or "").strip(),
        start_cmd=str(session.data.get("start_cmd") or "").strip(),
        codex_start_cmd=str(session.data.get("codex_start_cmd") or "").strip(),
    )


def requested_binding(*, log_path: str | None, session_id: str | None) -> RequestedBinding:
    path = str(log_path or "").strip()
    return RequestedBinding(
        path=path,
        session_id=normalized_session_id(session_id, log_path_str=path),
    )


def should_record_binding_change(
    session,
    current: CurrentBindingState,
    requested: RequestedBinding,
    *,
    session_id: str | None,
    resume_start_cmd: str | None,
) -> bool:
    return any(
        (
            path_changed(session, requested.path),
            id_changed(session, session_id),
            resume_command_changed(current, resume_start_cmd),
        )
    )


def path_changed(session, new_path: str) -> bool:
    return bool(new_path and session.data.get("codex_session_path") != new_path)


def id_changed(session, session_id: str | None) -> bool:
    return bool(session_id and session.data.get("codex_session_id") != session_id)


def resume_command_changed(current: CurrentBindingState, resume_start_cmd: str | None) -> bool:
    if resume_start_cmd is None:
        return False
    return current.start_cmd != resume_start_cmd or current.codex_start_cmd != resume_start_cmd


def normalized_session_id(session_id: str | None, *, log_path_str: str) -> str:
    new_id = str(session_id or "").strip()
    if new_id or not log_path_str:
        return new_id
    try:
        return Path(log_path_str).stem
    except Exception:
        return ""


def record_binding_change(session, change: BindingChange) -> None:
    apply_current_binding(session.data, change)
    mark_old_binding(
        session.data,
        old_path=change.old_path,
        old_id=change.old_id,
        new_path=change.new_path,
        new_id=change.new_id,
    )


def apply_current_binding(data: dict[str, object], change: BindingChange) -> None:
    if change.new_path:
        data["codex_session_path"] = change.new_path
    if change.new_id:
        data["codex_session_id"] = change.new_id


def mark_old_binding(data: dict[str, object], *, old_path: str, old_id: str, new_path: str, new_id: str) -> None:
    if old_id and old_id != new_id:
        data["old_codex_session_id"] = old_id
    if old_path and (old_path != new_path or (old_id and old_id != new_id)):
        data["old_codex_session_path"] = old_path
    if old_path or old_id:
        data["old_updated_at"] = now_str()


def trigger_transfer_if_needed(session, change: BindingChange) -> None:
    if not change.old_path and not change.old_id:
        return
    try:
        from memory.transfer_runtime import maybe_auto_transfer

        old_path_obj = expanded_old_path(change.old_path)
        maybe_auto_transfer(
            provider="codex",
            work_dir=Path(session.work_dir),
            session_path=old_path_obj,
            session_id=change.old_id or None,
        )
    except Exception:
        pass


def mark_active(data: dict[str, object]) -> None:
    if data.get("active") is False:
        data["active"] = True


def expanded_old_path(old_path: str) -> Path | None:
    if not old_path:
        return None
    try:
        return Path(old_path).expanduser()
    except Exception:
        return None


__all__ = ["update_codex_log_binding"]
