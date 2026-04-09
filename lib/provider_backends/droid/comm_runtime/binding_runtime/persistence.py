from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

from project.identity import compute_ccb_project_id
from provider_sessions.files import safe_write_session
from .history import maybe_transfer_previous_binding, record_previous_binding


def _load_session_data(project_session_file: Path) -> dict[str, Any]:
    try:
        with project_session_file.open('r', encoding='utf-8', errors='replace') as handle:
            data = json.load(handle)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _binding_fields(data: dict[str, Any]) -> tuple[str, str]:
    return (
        str(data.get('droid_session_path') or '').strip(),
        str(data.get('droid_session_id') or '').strip(),
    )


def _apply_binding(
    data: dict[str, Any],
    *,
    session_path_str: str,
    session_id: str | None,
) -> tuple[bool, bool]:
    updated = False
    binding_changed = False
    if data.get('droid_session_path') != session_path_str:
        data['droid_session_path'] = session_path_str
        updated = True
        binding_changed = True
    if session_id and data.get('droid_session_id') != session_id:
        data['droid_session_id'] = session_id
        updated = True
        binding_changed = True
    return updated, binding_changed


def _ensure_project_id(data: dict[str, Any]) -> bool:
    if (data.get('ccb_project_id') or '').strip():
        return False
    try:
        wd = data.get('work_dir')
        if isinstance(wd, str) and wd.strip():
            data['ccb_project_id'] = compute_ccb_project_id(Path(wd.strip()))
            return True
    except Exception:
        pass
    return False


def _resolve_session_id(session_path_str: str, session_id: str | None) -> str:
    resolved = str(session_id or '').strip()
    if resolved:
        return resolved
    try:
        return Path(session_path_str).stem
    except Exception:
        return ''


def remember_droid_session_binding(
    *,
    project_session_file: Path,
    session_path: Path,
    session_id_loader: Callable[[Path], tuple[Optional[str], Optional[str]]],
) -> dict[str, Any] | None:
    data = _load_session_data(project_session_file)
    old_path, old_id = _binding_fields(data)
    session_path_str = str(session_path)

    _cwd, session_id = session_id_loader(session_path)
    updated, binding_changed = _apply_binding(
        data,
        session_path_str=session_path_str,
        session_id=session_id,
    )
    updated = _ensure_project_id(data) or updated
    if not updated:
        return data

    new_id = _resolve_session_id(session_path_str, session_id)
    record_previous_binding(
        data,
        old_path=old_path,
        old_id=old_id,
        new_path=session_path_str,
        new_id=new_id,
        binding_changed=binding_changed,
    )
    maybe_transfer_previous_binding(
        data,
        old_path=old_path,
        old_id=old_id,
        binding_changed=binding_changed,
    )

    payload = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    safe_write_session(project_session_file, payload)
    return data


__all__ = ['remember_droid_session_binding']
