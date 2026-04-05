from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .history_transfer import apply_old_binding_metadata
from .persistence import write_project_session
from ..project_hash import read_gemini_session_id
from project_id import compute_ccb_project_id


@dataclass(frozen=True)
class GeminiBindingState:
    session_path: str
    session_id: str
    ccb_project_id: str


def update_project_session_binding(*, project_file: Path, session_path: Path) -> GeminiBindingState | None:
    if not project_file.exists():
        return None
    try:
        with project_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None

    updated = False
    old_path = str(data.get("gemini_session_path") or "").strip()
    old_id = str(data.get("gemini_session_id") or "").strip()
    session_path_str = str(session_path)
    binding_changed = False
    if data.get("gemini_session_path") != session_path_str:
        data["gemini_session_path"] = session_path_str
        updated = True
        binding_changed = True

    ccb_project_id = ensure_project_id(data)
    if ccb_project_id and data.get("ccb_project_id") != ccb_project_id:
        data["ccb_project_id"] = ccb_project_id
        updated = True

    try:
        project_hash = session_path.parent.parent.name
    except Exception:
        project_hash = ""
    if project_hash and data.get("gemini_project_hash") != project_hash:
        data["gemini_project_hash"] = project_hash
        updated = True

    session_id = read_gemini_session_id(session_path)
    if session_id and data.get("gemini_session_id") != session_id:
        data["gemini_session_id"] = session_id
        updated = True
        binding_changed = True

    if updated:
        apply_old_binding_metadata(
            data,
            old_path=old_path,
            old_id=old_id,
            new_path=session_path_str,
            new_id=session_id,
            binding_changed=binding_changed,
        )
        write_project_session(project_file, data)

    return GeminiBindingState(
        session_path=session_path_str,
        session_id=session_id,
        ccb_project_id=str(data.get("ccb_project_id") or "").strip(),
    )


def ensure_project_id(data: dict[str, Any]) -> str:
    current = str(data.get("ccb_project_id") or "").strip()
    if current:
        return current
    try:
        wd = data.get("work_dir")
        if isinstance(wd, str) and wd.strip():
            return compute_ccb_project_id(Path(wd.strip()))
    except Exception:
        return ""
    return ""


__all__ = [
    "GeminiBindingState",
    "ensure_project_id",
    "update_project_session_binding",
]
