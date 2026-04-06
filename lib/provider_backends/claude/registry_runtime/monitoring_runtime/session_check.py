from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional


def check_one(
    registry,
    key: str,
    work_dir: Path,
    *,
    now: float,
    refresh_interval_s: float,
    scan_limit: int,
    find_session_file_fn: Callable[[Path], Optional[Path]],
    load_session_fn: Callable[[Path], object | None],
    refresh_claude_log_binding_fn,
    write_log_fn: Callable[[str], None],
) -> None:
    session_file = find_session_file_fn(work_dir)
    exists = _session_file_exists(session_file)
    if not exists:
        _mark_missing_session_file(registry, key, work_dir, now=now, write_log_fn=write_log_fn)
        return
    current_mtime = _session_mtime(session_file)
    session, file_changed = load_or_reuse_session(
        registry,
        key,
        work_dir,
        session_file=session_file,
        current_mtime=current_mtime,
        load_session_fn=load_session_fn,
    )
    if not session:
        _invalidate_entry(registry, key, now=now)
        return
    if not _ensure_session_pane(session):
        _mark_invalid_pane(registry, key, work_dir, now=now, write_log_fn=write_log_fn)
        return
    due, backoff = refresh_due(registry, key, now=now, refresh_interval_s=refresh_interval_s, file_changed=file_changed)
    if not due:
        return
    updated = refresh_log_binding(
        registry,
        session,
        file_changed=file_changed,
        scan_limit=scan_limit,
        refresh_claude_log_binding_fn=refresh_claude_log_binding_fn,
    )
    finalize_refresh(
        registry,
        key,
        session_file=session_file,
        now=now,
        refresh_interval_s=refresh_interval_s,
        updated=updated,
        backoff=backoff,
    )


def load_or_reuse_session(
    registry,
    key: str,
    work_dir: Path,
    *,
    session_file: Path,
    current_mtime: float,
    load_session_fn,
):
    session = None
    file_changed = False
    with registry._lock:
        entry = registry._sessions.get(key)
        if not entry or not entry.valid:
            return None, False
        file_changed = bool((entry.session_file != session_file) or (entry.file_mtime != current_mtime))
        if file_changed or entry.session is None:
            session = load_session_fn(work_dir)
            entry.session = session
            entry.session_file = session_file
            entry.file_mtime = current_mtime
        else:
            session = entry.session
    return session, file_changed


def refresh_due(registry, key: str, *, now: float, refresh_interval_s: float, file_changed: bool) -> tuple[bool, float]:
    with registry._lock:
        entry = registry._sessions.get(key)
        if not entry or not entry.valid:
            return False, refresh_interval_s
        due = now >= (entry.next_bind_refresh or 0.0)
        if not due and not file_changed:
            entry.last_check = now
            return False, refresh_interval_s
        return True, entry.bind_backoff_s or refresh_interval_s


def refresh_log_binding(registry, session, *, file_changed: bool, scan_limit: int, refresh_claude_log_binding_fn) -> bool:
    try:
        return bool(
            refresh_claude_log_binding_fn(
                session,
                root=registry._claude_root,
                scan_limit=scan_limit,
                force_scan=bool(file_changed),
            )
        )
    except Exception:
        return False


def finalize_refresh(registry, key: str, *, session_file: Path, now: float, refresh_interval_s: float, updated: bool, backoff: float) -> None:
    with registry._lock:
        entry = registry._sessions.get(key)
        if not entry or not entry.valid:
            return
        entry.bind_backoff_s = refresh_interval_s if updated else min(600.0, max(refresh_interval_s, backoff * 2.0))
        entry.next_bind_refresh = now + entry.bind_backoff_s
        try:
            entry.file_mtime = session_file.stat().st_mtime
        except Exception:
            pass
        entry.last_check = now


def _session_file_exists(session_file: Path | None) -> bool:
    try:
        return bool(session_file and session_file.exists())
    except Exception:
        return False


def _session_mtime(session_file: Path | None) -> float:
    try:
        return session_file.stat().st_mtime if session_file else 0.0
    except Exception:
        return 0.0


def _ensure_session_pane(session) -> bool:
    try:
        ok, _ = session.ensure_pane()
    except Exception:
        return False
    return bool(ok)


def _invalidate_entry(registry, key: str, *, now: float) -> None:
    with registry._lock:
        entry = registry._sessions.get(key)
        if entry and entry.valid:
            entry.valid = False
            entry.last_check = now


def _mark_missing_session_file(registry, key: str, work_dir: Path, *, now: float, write_log_fn: Callable[[str], None]) -> None:
    with registry._lock:
        entry = registry._sessions.get(key)
        if entry and entry.valid:
            write_log_fn(f'[WARN] Session file deleted: {work_dir}')
            entry.valid = False
            entry.last_check = now


def _mark_invalid_pane(registry, key: str, work_dir: Path, *, now: float, write_log_fn: Callable[[str], None]) -> None:
    with registry._lock:
        entry = registry._sessions.get(key)
        if entry and entry.valid:
            write_log_fn(f'[WARN] Session pane invalid: {work_dir}')
            entry.valid = False
            entry.last_check = now


__all__ = [
    'check_one',
    'finalize_refresh',
    'load_or_reuse_session',
    'refresh_due',
    'refresh_log_binding',
]
