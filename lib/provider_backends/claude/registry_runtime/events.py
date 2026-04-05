from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from provider_backends.claude.registry_support.logs import parse_sessions_index, should_overwrite_binding
from provider_backends.claude.registry_support.pathing import path_within
from provider_backends.claude.session import load_project_session

from .session_updates import read_log_meta_with_retry, update_session_file_direct


def handle_new_log_file_global(registry: Any, path: Path) -> None:
    if path.name == "sessions-index.json":
        handle_sessions_index(registry, str(path.parent), path)
        return
    if not path.exists():
        return
    cwd, sid, is_sidechain = read_log_meta_with_retry(path)
    if is_sidechain is True or not cwd:
        return
    session_id = sid or path.stem
    if not session_id:
        return
    work_dir = Path(cwd)
    session_file = registry._find_claude_session_file(work_dir)
    if session_file:
        update_session_file_direct(session_file, path, session_id)

    key = str(work_dir)
    with registry._lock:
        entry = registry._sessions.get(key)
        session = entry.session if entry else None
    if session:
        try:
            session.update_claude_binding(session_path=path, session_id=session_id)
        except Exception:
            pass


def handle_new_log_file(registry: Any, project_key: str, path: Path) -> None:
    if path.name == "sessions-index.json":
        handle_sessions_index(registry, project_key, path)
        return
    if not path.exists():
        return
    now = time.time()
    path_key = str(path)
    with registry._lock:
        last_check = registry._log_last_check.get(path_key, 0.0)
        if now - last_check < 0.4:
            return
        registry._log_last_check[path_key] = now
        for pending_path, ts in list(registry._pending_logs.items()):
            if now - ts > 120:
                registry._pending_logs.pop(pending_path, None)

    cwd, sid, is_sidechain = read_log_meta_with_retry(path)
    if is_sidechain is True:
        with registry._lock:
            registry._pending_logs.pop(path_key, None)
        return
    session_id = sid or path.stem
    if not session_id:
        return

    with registry._lock:
        watcher_entry = registry._watchers.get(project_key)
        if not watcher_entry:
            return
        keys = list(watcher_entry.keys)
        entries = [(key, registry._sessions.get(key)) for key in keys]

    if not cwd:
        updated_any = False
        for _key, entry in entries:
            if not entry or not entry.valid:
                continue
            session = entry.session or load_project_session(entry.work_dir)
            if not session:
                continue
            current_path = Path(session.claude_session_path).expanduser() if session.claude_session_path else None
            if not should_overwrite_binding(current_path, path) and session.claude_session_id == session_id:
                continue
            try:
                session.update_claude_binding(session_path=path, session_id=session_id)
                updated_any = True
            except Exception:
                pass
        if updated_any:
            with registry._lock:
                registry._pending_logs.pop(path_key, None)
        else:
            with registry._lock:
                registry._pending_logs[path_key] = now
        return

    updated_any = False
    for _key, entry in entries:
        if not entry or not entry.valid:
            continue
        if cwd and not path_within(cwd, str(entry.work_dir)):
            continue
        session = entry.session or load_project_session(entry.work_dir)
        if not session:
            continue
        try:
            session.update_claude_binding(session_path=path, session_id=session_id)
            updated_any = True
        except Exception:
            pass
    if updated_any:
        with registry._lock:
            registry._pending_logs.pop(path_key, None)


def handle_sessions_index(registry: Any, project_key: str, index_path: Path) -> None:
    if not index_path.exists():
        return
    with registry._lock:
        watcher_entry = registry._watchers.get(project_key)
        if not watcher_entry:
            return
        keys = list(watcher_entry.keys)
        entries = [(key, registry._sessions.get(key)) for key in keys]

    for _key, entry in entries:
        if not entry:
            continue
        work_dir = entry.work_dir
        session_path = parse_sessions_index(work_dir, root=registry._claude_root)
        if not session_path or not session_path.exists():
            continue
        session_id = session_path.stem
        session_file = registry._find_claude_session_file(work_dir)
        if session_file:
            update_session_file_direct(session_file, session_path, session_id)
        session = entry.session or load_project_session(work_dir)
        if not session:
            continue
        try:
            session.update_claude_binding(session_path=session_path, session_id=session_id)
        except Exception:
            pass
