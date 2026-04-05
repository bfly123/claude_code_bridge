from __future__ import annotations

from pathlib import Path


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
    if not path or not path.exists():
        return
    try:
        project_hash = path.parent.parent.name
    except Exception:
        project_hash = ""
    if not project_hash:
        return
    work_dirs = work_dirs_for_hash(project_hash, root=gemini_root)
    if not work_dirs:
        return
    session_id = session_id_reader(path)
    for work_dir in work_dirs:
        session_file = session_file_finder(work_dir)
        if not session_file or not session_file.exists():
            continue
        session = session_loader(work_dir)
        if not session:
            continue
        try:
            session.update_gemini_binding(session_path=path, session_id=session_id or None)
        except Exception:
            continue


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
    if not has_watchdog:
        return watcher, started
    if started:
        return watcher, started
    with lock:
        if started:
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
