from __future__ import annotations

from pathlib import Path

from provider_core.session_binding_runtime import resolve_bound_instance


def gemini_watch_predicate(path: Path) -> bool:
    return path.suffix == ".json" and path.name.startswith("session-")


def handle_gemini_session_event(
    path: Path,
    *,
    gemini_root: Path,
    work_dirs_for_hash,
    session_id_reader,
    session_file_finder,
    session_loader,
) -> None:
    if not is_existing_session_path(path):
        return
    project_hash = session_project_hash(path)
    if not project_hash:
        return
    work_dirs = work_dirs_for_hash(project_hash, root=gemini_root)
    if not work_dirs:
        return
    session_id = session_id_reader(path)
    update_project_sessions(
        path=path,
        session_id=session_id,
        work_dirs=work_dirs,
        provider="gemini",
        base_filename=".gemini-session",
        session_file_finder=session_file_finder,
        session_loader=session_loader,
    )


def ensure_gemini_watchdog_started(
    *,
    has_watchdog: bool,
    started: bool,
    lock,
    gemini_root: Path,
    watcher_factory,
    event_handler,
    watcher=None,
):
    if not should_start_watchdog(has_watchdog=has_watchdog, started=started):
        return watcher, started
    with lock:
        if not should_start_watchdog(has_watchdog=has_watchdog, started=started):
            return watcher, started
        if not gemini_root.exists():
            return watcher, started
        instance = watcher_factory(
            gemini_root,
            event_handler,
            recursive=True,
            predicate=gemini_watch_predicate,
        )
        try:
            instance.start()
        except Exception:
            return watcher, started
        return instance, True


def is_existing_session_path(path: Path | None) -> bool:
    return bool(path and path.exists())


def session_project_hash(path: Path) -> str:
    try:
        return path.parent.parent.name
    except Exception:
        return ""


def update_project_sessions(
    *,
    path: Path,
    session_id: str,
    work_dirs,
    provider: str,
    base_filename: str,
    session_file_finder,
    session_loader,
) -> None:
    for work_dir in work_dirs:
        session = load_bound_session(
            work_dir,
            provider=provider,
            base_filename=base_filename,
            session_file_finder=session_file_finder,
            session_loader=session_loader,
        )
        if session is None:
            continue
        try:
            session.update_gemini_binding(session_path=path, session_id=session_id or None)
        except Exception:
            continue


def load_bound_session(work_dir, *, provider: str, base_filename: str, session_file_finder, session_loader):
    instance = resolve_bound_instance(
        provider=provider,
        base_filename=base_filename,
        work_dir=work_dir,
        allow_env=False,
    )
    session_file = session_file_finder(work_dir, instance)
    if not session_file or not session_file.exists():
        return None
    return session_loader(work_dir, instance)


def should_start_watchdog(*, has_watchdog: bool, started: bool) -> bool:
    return bool(has_watchdog and not started)
