from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from provider_backends.claude.registry_support.logs import should_overwrite_binding
from provider_backends.claude.registry_support.pathing import path_within

from ..session_updates import read_log_meta_with_retry
from .common import load_session_for_entry, safe_update_binding, watcher_entries
from .sessions_index import handle_sessions_index

_LOG_RECHECK_WINDOW_S = 0.4
_PENDING_LOG_TTL_S = 120.0


def handle_new_log_file(registry: Any, project_key: str, path: Path) -> None:
    if path.name == "sessions-index.json":
        handle_sessions_index(registry, project_key, path)
        return
    if not path.exists():
        return

    now = time.time()
    if not _should_process_log_path(registry, path, now=now):
        return

    cwd, sid, is_sidechain = read_log_meta_with_retry(path)
    path_key = str(path)
    if is_sidechain is True:
        _clear_pending_log(registry, path_key)
        return
    session_id = sid or path.stem
    if not session_id:
        return

    entries = watcher_entries(registry, project_key)
    if not entries:
        return
    if not cwd:
        _handle_unscoped_log(registry, entries, path, path_key=path_key, session_id=session_id, now=now)
        return
    _handle_scoped_log(registry, entries, path, path_key=path_key, session_id=session_id, cwd=cwd)


def _should_process_log_path(registry: Any, path: Path, *, now: float) -> bool:
    path_key = str(path)
    with registry._lock:
        last_check = registry._log_last_check.get(path_key, 0.0)
        if now - last_check < _LOG_RECHECK_WINDOW_S:
            return False
        registry._log_last_check[path_key] = now
        for pending_path, ts in list(registry._pending_logs.items()):
            if now - ts > _PENDING_LOG_TTL_S:
                registry._pending_logs.pop(pending_path, None)
    return True


def _handle_unscoped_log(
    registry: Any,
    entries: list[tuple[str, Any]],
    path: Path,
    *,
    path_key: str,
    session_id: str,
    now: float,
) -> None:
    updated_any = False
    for _key, entry in entries:
        if not entry or not entry.valid:
            continue
        session = load_session_for_entry(registry, entry)
        if not session:
            continue
        current_path = Path(session.claude_session_path).expanduser() if session.claude_session_path else None
        if not should_overwrite_binding(current_path, path) and session.claude_session_id == session_id:
            continue
        updated_any = safe_update_binding(session, session_path=path, session_id=session_id) or updated_any
    _set_pending_state(registry, path_key, updated=updated_any, now=now)


def _handle_scoped_log(
    registry: Any,
    entries: list[tuple[str, Any]],
    path: Path,
    *,
    path_key: str,
    session_id: str,
    cwd: str,
) -> None:
    updated_any = False
    for _key, entry in entries:
        if not entry or not entry.valid:
            continue
        if not path_within(cwd, str(entry.work_dir)):
            continue
        session = load_session_for_entry(registry, entry)
        if not session:
            continue
        updated_any = safe_update_binding(session, session_path=path, session_id=session_id) or updated_any
    if updated_any:
        _clear_pending_log(registry, path_key)


def _set_pending_state(registry: Any, path_key: str, *, updated: bool, now: float) -> None:
    if updated:
        _clear_pending_log(registry, path_key)
        return
    with registry._lock:
        registry._pending_logs[path_key] = now


def _clear_pending_log(registry: Any, path_key: str) -> None:
    with registry._lock:
        registry._pending_logs.pop(path_key, None)


__all__ = ["handle_new_log_file"]
