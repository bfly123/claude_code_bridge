from __future__ import annotations

from pathlib import Path
from typing import Any

from pane_registry_runtime import upsert_registry
from project.identity import compute_ccb_project_id


def publish_droid_registry(
    *,
    session_info: dict[str, Any],
    ccb_session_id: str,
    terminal: str,
    pane_id: str | None,
    project_session_file: str | None,
) -> None:
    try:
        upsert_registry(_registry_payload(
            session_info,
            ccb_session_id=ccb_session_id,
            terminal=terminal,
            pane_id=pane_id,
            project_session_file=project_session_file,
        ))
    except Exception:
        pass


def _registry_payload(
    session_info: dict[str, Any],
    *,
    ccb_session_id: str,
    terminal: str,
    pane_id: str | None,
    project_session_file: str | None,
) -> dict[str, Any]:
    wd = session_info.get('work_dir')
    return {
        'ccb_session_id': ccb_session_id,
        'ccb_project_id': _project_id_for_work_dir(wd),
        'work_dir': wd,
        'terminal': terminal,
        'providers': {
            'droid': {
                'pane_id': pane_id or None,
                'pane_title_marker': session_info.get('pane_title_marker'),
                'session_file': project_session_file,
                'droid_session_id': session_info.get('droid_session_id'),
                'droid_session_path': session_info.get('droid_session_path'),
            }
        },
    }


def _project_id_for_work_dir(work_dir) -> str | None:
    if not isinstance(work_dir, str) or not work_dir:
        return None
    try:
        return compute_ccb_project_id(Path(work_dir)) or None
    except Exception:
        return None


__all__ = ['publish_droid_registry']
