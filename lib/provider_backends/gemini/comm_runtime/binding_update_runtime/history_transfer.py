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
    normalized_new_id = new_id
    if not normalized_new_id and new_path:
        try:
            normalized_new_id = Path(new_path).stem
        except Exception:
            normalized_new_id = ""
    if old_id and old_id != normalized_new_id:
        data["old_gemini_session_id"] = old_id
    if old_path and (old_path != new_path or (old_id and old_id != normalized_new_id)):
        data["old_gemini_session_path"] = old_path
    if (old_path or old_id) and binding_changed:
        data["old_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        maybe_transfer_old_binding(old_path=old_path, old_id=old_id, work_dir_hint=data.get("work_dir"))


def maybe_transfer_old_binding(*, old_path: str, old_id: str, work_dir_hint: Any) -> None:
    try:
        from memory.transfer_runtime import maybe_auto_transfer

        old_path_obj = None
        if old_path:
            try:
                old_path_obj = Path(old_path).expanduser()
            except Exception:
                old_path_obj = None
        work_dir = Path(work_dir_hint) if isinstance(work_dir_hint, str) and work_dir_hint else Path.cwd()
        maybe_auto_transfer(
            provider="gemini",
            work_dir=work_dir,
            session_path=old_path_obj,
            session_id=old_id or None,
        )
    except Exception:
        pass


__all__ = [
    "apply_old_binding_metadata",
    "maybe_transfer_old_binding",
]
