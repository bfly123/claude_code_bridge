from __future__ import annotations

import time
from pathlib import Path

from pane_registry_runtime import upsert_registry
from project.identity import compute_ccb_project_id
from provider_sessions.files import safe_write_session

from ..registry_support.pathing import ensure_claude_session_work_dir_fields, infer_work_dir_from_session_file
from .binding_runtime import publish_claude_registry as _publish_claude_registry_impl
from .binding_runtime import remember_claude_session_binding as _remember_claude_session_binding_impl


def remember_claude_session_binding(
    *,
    project_session_file: Path,
    session_path: Path,
    session_info,
):
    return _remember_claude_session_binding_impl(
        project_session_file=project_session_file,
        session_path=session_path,
        session_info=session_info,
        infer_work_dir_from_session_file_fn=infer_work_dir_from_session_file,
        ensure_claude_session_work_dir_fields_fn=ensure_claude_session_work_dir_fields,
        safe_write_session_fn=safe_write_session,
        now_str_fn=_now_str,
    )


def publish_claude_registry(
    *,
    session_info,
    terminal: str,
    pane_id: str | None,
    project_session_file: str | None,
) -> None:
    _publish_claude_registry_impl(
        session_info=session_info,
        terminal=terminal,
        pane_id=pane_id,
        project_session_file=project_session_file,
        compute_ccb_project_id_fn=compute_ccb_project_id,
        upsert_registry_fn=upsert_registry,
        cwd_fn=Path.cwd,
    )


def _now_str() -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S')


__all__ = ['publish_claude_registry', 'remember_claude_session_binding']
