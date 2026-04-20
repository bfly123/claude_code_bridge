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
    if _handle_sessions_index_path(registry, project_key, path):
        return
    log_update = _load_log_update(registry, path)
    if log_update is None:
        return
    entries = watcher_entries(registry, project_key)
    if not entries:
        return
    if log_update.cwd is None:
        _handle_unscoped_log(registry, entries, log_update)
        return
    _handle_scoped_log(registry, entries, log_update)


def _handle_sessions_index_path(registry: Any, project_key: str, path: Path) -> bool:
    if path.name != "sessions-index.json":
        return False
    handle_sessions_index(registry, project_key, path)
    return True


def _load_log_update(registry: Any, path: Path):
    if not path.exists():
        return None
    now = time.time()
    if not _should_process_log_path(registry, path, now=now):
        return None
    cwd, sid, is_sidechain = read_log_meta_with_retry(path)
    path_key = str(path)
    if is_sidechain is True:
        _clear_pending_log(registry, path_key)
        return None
    session_id = sid or path.stem
    if not session_id:
        return None
    return _ProjectLogUpdate(
        path=path,
        path_key=path_key,
        session_id=session_id,
        cwd=_normalized_cwd(cwd),
        now=now,
    )


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
    log_update,
) -> None:
    updated_any = False
    for _key, entry in entries:
        session = _unscoped_session_candidate(registry, entry)
        if session is None:
            continue
        if not _should_update_unscoped_session(session, log_update):
            continue
        updated_any = safe_update_binding(
            session,
            session_path=log_update.path,
            session_id=log_update.session_id,
        ) or updated_any
    _set_pending_state(registry, log_update.path_key, updated=updated_any, now=log_update.now)


def _handle_scoped_log(
    registry: Any,
    entries: list[tuple[str, Any]],
    log_update,
) -> None:
    updated_any = False
    for _key, entry in entries:
        session = _scoped_session_candidate(registry, entry, cwd=log_update.cwd)
        if session is None:
            continue
        updated_any = safe_update_binding(
            session,
            session_path=log_update.path,
            session_id=log_update.session_id,
        ) or updated_any
    if updated_any:
        _clear_pending_log(registry, log_update.path_key)


def _unscoped_session_candidate(registry: Any, entry):
    if not _valid_entry(entry):
        return None
    return load_session_for_entry(registry, entry)


def _scoped_session_candidate(registry: Any, entry, *, cwd: str | None):
    if not (_valid_entry(entry) and cwd and path_within(cwd, str(entry.work_dir))):
        return None
    return load_session_for_entry(registry, entry)


def _valid_entry(entry) -> bool:
    return bool(entry and entry.valid)


def _should_update_unscoped_session(session, log_update) -> bool:
    current_path = _claude_session_path(session)
    if should_overwrite_binding(current_path, log_update.path):
        return True
    return session.claude_session_id != log_update.session_id


def _claude_session_path(session) -> Path | None:
    path = str(session.claude_session_path or '').strip()
    return Path(path).expanduser() if path else None


class _ProjectLogUpdate:
    def __init__(self, *, path: Path, path_key: str, session_id: str, cwd: str | None, now: float) -> None:
        self.path = path
        self.path_key = path_key
        self.session_id = session_id
        self.cwd = cwd
        self.now = now


def _normalized_cwd(cwd) -> str | None:
    if not isinstance(cwd, str):
        return None
    text = cwd.strip()
    return text or None


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
