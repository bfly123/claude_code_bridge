from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project.identity import compute_ccb_project_id

from ..project_hash import read_gemini_session_id
from .history_transfer import apply_old_binding_metadata
from .persistence import write_project_session


@dataclass(frozen=True)
class GeminiBindingState:
    session_path: str
    session_id: str
    ccb_project_id: str


@dataclass(frozen=True)
class GeminiBindingChange:
    old_path: str
    old_id: str
    session_path: str
    session_id: str
    project_id: str
    project_hash: str
    binding_changed: bool


def update_project_session_binding(*, project_file: Path, session_path: Path) -> GeminiBindingState | None:
    data = load_project_session_data(project_file)
    if data is None:
        return None

    change = binding_change(data, session_path=session_path)
    if change is not None:
        apply_binding_change(data, change)
        write_project_session(project_file, data)

    return GeminiBindingState(
        session_path=str(session_path),
        session_id=str(data.get("gemini_session_id") or "").strip(),
        ccb_project_id=str(data.get("ccb_project_id") or "").strip(),
    )


def load_project_session_data(project_file: Path) -> dict[str, Any] | None:
    if not project_file.exists():
        return None
    try:
        with project_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def binding_change(data: dict[str, Any], *, session_path: Path) -> GeminiBindingChange | None:
    old_path = str(data.get("gemini_session_path") or "").strip()
    old_id = str(data.get("gemini_session_id") or "").strip()
    new_path = str(session_path)
    project_id = ensure_project_id(data)
    project_hash = extract_project_hash(session_path)
    session_id = read_gemini_session_id(session_path)
    binding_changed = binding_path_changed(data, new_path) or binding_session_changed(data, session_id)
    if not any(
        (
            binding_changed,
            project_id_changed(data, project_id),
            project_hash_changed(data, project_hash),
        )
    ):
        return None
    return GeminiBindingChange(
        old_path=old_path,
        old_id=old_id,
        session_path=new_path,
        session_id=session_id,
        project_id=project_id,
        project_hash=project_hash,
        binding_changed=binding_changed,
    )


def binding_path_changed(data: dict[str, Any], new_path: str) -> bool:
    return data.get("gemini_session_path") != new_path


def binding_session_changed(data: dict[str, Any], session_id: str) -> bool:
    return bool(session_id and data.get("gemini_session_id") != session_id)


def project_id_changed(data: dict[str, Any], project_id: str) -> bool:
    return bool(project_id and data.get("ccb_project_id") != project_id)


def project_hash_changed(data: dict[str, Any], project_hash: str) -> bool:
    return bool(project_hash and data.get("gemini_project_hash") != project_hash)


def apply_binding_change(data: dict[str, Any], change: GeminiBindingChange) -> None:
    data["gemini_session_path"] = change.session_path
    if change.project_id:
        data["ccb_project_id"] = change.project_id
    if change.project_hash:
        data["gemini_project_hash"] = change.project_hash
    if change.session_id:
        data["gemini_session_id"] = change.session_id
    apply_old_binding_metadata(
        data,
        old_path=change.old_path,
        old_id=change.old_id,
        new_path=change.session_path,
        new_id=change.session_id,
        binding_changed=change.binding_changed,
    )


def ensure_project_id(data: dict[str, Any]) -> str:
    current = str(data.get("ccb_project_id") or "").strip()
    if current:
        return current
    try:
        work_dir = data.get("work_dir")
        if isinstance(work_dir, str) and work_dir.strip():
            return compute_ccb_project_id(Path(work_dir.strip()))
    except Exception:
        return ""
    return ""


def extract_project_hash(session_path: Path) -> str:
    try:
        return session_path.parent.parent.name
    except Exception:
        return ""


__all__ = ["GeminiBindingState", "ensure_project_id", "update_project_session_binding"]
