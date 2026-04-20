from __future__ import annotations

import time
from pathlib import Path
from typing import Any


def apply_old_binding_metadata(
    data: dict[str, Any],
    *,
    old_path: str,
    old_id: str,
    new_path: str,
    new_id: str,
    binding_changed: bool,
) -> None:
    normalized_new_id = _normalized_session_id(new_id=new_id, new_path=new_path)
    replaced_binding = bool(old_id and old_id != normalized_new_id)
    replaced_path = bool(old_path and (old_path != new_path or replaced_binding))

    if replaced_binding:
        data["old_gemini_session_id"] = old_id
    if replaced_path:
        data["old_gemini_session_path"] = old_path

    if not _should_transfer_old_binding(old_path=old_path, old_id=old_id, binding_changed=binding_changed):
        return

    data["old_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    maybe_transfer_old_binding(old_path=old_path, old_id=old_id, work_dir_hint=data.get("work_dir"))


def maybe_transfer_old_binding(*, old_path: str, old_id: str, work_dir_hint: Any) -> None:
    try:
        from memory.transfer_runtime import maybe_auto_transfer

        maybe_auto_transfer(
            provider="gemini",
            work_dir=_resolve_work_dir(work_dir_hint),
            session_path=_resolve_session_path(old_path),
            session_id=old_id or None,
        )
    except Exception:
        pass


def _normalized_session_id(*, new_id: str, new_path: str) -> str:
    if new_id:
        return new_id
    if not new_path:
        return ""
    try:
        return Path(new_path).stem
    except Exception:
        return ""


def _should_transfer_old_binding(*, old_path: str, old_id: str, binding_changed: bool) -> bool:
    return bool((old_path or old_id) and binding_changed)


def _resolve_work_dir(work_dir_hint: Any) -> Path:
    if isinstance(work_dir_hint, str) and work_dir_hint:
        return Path(work_dir_hint)
    return Path.cwd()


def _resolve_session_path(old_path: str) -> Path | None:
    if not old_path:
        return None
    try:
        return Path(old_path).expanduser()
    except Exception:
        return None


__all__ = ["apply_old_binding_metadata", "maybe_transfer_old_binding"]
