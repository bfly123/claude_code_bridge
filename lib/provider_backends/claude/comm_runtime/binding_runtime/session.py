from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


def remember_claude_session_binding(
    *,
    project_session_file: Path,
    session_path: Path,
    session_info: dict[str, Any],
    infer_work_dir_from_session_file_fn: Callable[[Path], Path],
    ensure_claude_session_work_dir_fields_fn: Callable[[dict, Path], Path | None],
    safe_write_session_fn: Callable[[Path, str], tuple[bool, str | None]],
    now_str_fn: Callable[[], str],
) -> dict[str, Any] | None:
    if not project_session_file.exists():
        return None
    data = _load_session_payload(project_session_file)
    _assign_work_dir(
        data,
        session_info=session_info,
        project_session_file=project_session_file,
        infer_work_dir_from_session_file_fn=infer_work_dir_from_session_file_fn,
    )
    ensure_claude_session_work_dir_fields_fn(data, project_session_file)
    _update_binding_fields(data, session_path=session_path, now_str_fn=now_str_fn)
    payload = _render_session_payload(data)
    ok, _err = safe_write_session_fn(project_session_file, payload)
    if not ok:
        return None
    return data


def _assign_work_dir(
    data: dict[str, Any],
    *,
    session_info: dict[str, Any],
    project_session_file: Path,
    infer_work_dir_from_session_file_fn: Callable[[Path], Path],
) -> None:
    work_dir = _resolve_work_dir(
        data,
        session_info=session_info,
        project_session_file=project_session_file,
        infer_work_dir_from_session_file_fn=infer_work_dir_from_session_file_fn,
    )
    if work_dir:
        data['work_dir'] = work_dir


def _resolve_work_dir(
    data: dict[str, Any],
    *,
    session_info: dict[str, Any],
    project_session_file: Path,
    infer_work_dir_from_session_file_fn: Callable[[Path], Path],
) -> str:
    work_dir = str(data.get('work_dir') or '').strip()
    if work_dir:
        return work_dir
    raw_hint = session_info.get('work_dir')
    if isinstance(raw_hint, str) and raw_hint.strip():
        return raw_hint.strip()
    return str(infer_work_dir_from_session_file_fn(project_session_file))


def _update_binding_fields(
    data: dict[str, Any],
    *,
    session_path: Path,
    now_str_fn: Callable[[], str],
) -> None:
    current = _binding_snapshot(data)
    new_path = str(session_path)
    new_id = str(session_path.stem or '').strip()
    timestamp = now_str_fn()
    _assign_current_binding(data, session_path_str=new_path, session_id=new_id)
    _assign_binding_history(
        data,
        current=current,
        session_path_str=new_path,
        session_id=new_id,
        timestamp=timestamp,
    )
    data['updated_at'] = timestamp
    data['active'] = True


def _binding_snapshot(data: dict[str, Any]) -> dict[str, str]:
    return {
        'session_path': str(data.get('claude_session_path') or '').strip(),
        'session_id': str(data.get('claude_session_id') or '').strip(),
    }


def _assign_current_binding(
    data: dict[str, Any],
    *,
    session_path_str: str,
    session_id: str,
) -> None:
    data['claude_session_path'] = session_path_str
    if session_id and data.get('claude_session_id') != session_id:
        data['claude_session_id'] = session_id


def _assign_binding_history(
    data: dict[str, Any],
    *,
    current: dict[str, str],
    session_path_str: str,
    session_id: str,
    timestamp: str,
) -> None:
    path_changed = bool(current['session_path'] and current['session_path'] != session_path_str)
    id_changed = bool(current['session_id'] and current['session_id'] != session_id)
    if id_changed:
        data['old_claude_session_id'] = current['session_id']
    if path_changed:
        data['old_claude_session_path'] = current['session_path']
    if id_changed or path_changed:
        data['old_updated_at'] = timestamp


def _render_session_payload(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def _load_session_payload(path: Path) -> dict[str, Any]:
    try:
        with path.open('r', encoding='utf-8-sig', errors='replace') as handle:
            payload = json.load(handle)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


__all__ = ['remember_claude_session_binding']
