from __future__ import annotations

import os
from pathlib import Path

from opencode_runtime.paths import OPENCODE_STORAGE_ROOT
from opencode_runtime.storage import OpenCodeStorageAccessor

from ..reader_support import allow_any_session as _allow_any_session
from ..reader_support import allow_git_root_fallback as _allow_git_root_fallback
from ..reader_support import allow_parent_workdir_match as _allow_parent_workdir_match
from ..reader_support import allow_session_rollover as _allow_session_rollover
from ..reader_support import fallback_project_id as _fallback_project_id
from .config import bounded_force_read_interval, bounded_poll_interval


def initialize_reader(
    reader,
    *,
    root=None,
    work_dir=None,
    project_id: str,
    session_id_filter: str | None,
) -> None:
    reader.root = Path(root or OPENCODE_STORAGE_ROOT).expanduser()
    reader._storage = OpenCodeStorageAccessor(reader.root)
    reader.work_dir = work_dir or Path.cwd()
    env_project_id = (os.environ.get("OPENCODE_PROJECT_ID") or "").strip()
    explicit_project_id = bool(env_project_id) or ((project_id or "").strip() not in ("", "global"))
    reader._allow_parent_match = _allow_parent_workdir_match()
    reader._allow_any_session = _allow_any_session()
    reader._allow_session_rollover = _allow_session_rollover()
    reader.project_id = (env_project_id or project_id or "global").strip() or "global"
    reader._session_id_filter = (session_id_filter or "").strip() or None
    apply_project_scope(reader, explicit_project_id=explicit_project_id, allow_git_root_fallback=_allow_git_root_fallback())
    reader._poll_interval = bounded_poll_interval()
    reader._force_read_interval = bounded_force_read_interval()


def apply_project_scope(reader, *, explicit_project_id: bool, allow_git_root_fallback: bool) -> None:
    if explicit_project_id:
        return
    detected = reader._detect_project_id_for_workdir()
    if detected:
        reader.project_id = detected
        return
    if allow_git_root_fallback:
        reader.project_id = _fallback_project_id(reader.work_dir)


__all__ = ['apply_project_scope', 'initialize_reader']
