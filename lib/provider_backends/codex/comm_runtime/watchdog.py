from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def handle_codex_log_event(
    path: Path,
    *,
    cwd_extractor: Callable[[Path], str | None],
    session_resolver: Callable[[Path], tuple[Path | None, str | None]],
    session_loader: Callable[[Path, str | None], Any],
    session_id_extractor: Callable[[Path], str | None],
) -> None:
    if not path or not path.exists() or path.suffix != ".jsonl":
        return
    cwd = cwd_extractor(path)
    if not cwd:
        return
    try:
        work_dir = Path(cwd).expanduser()
    except Exception:
        return
    session_file, instance = session_resolver(work_dir)
    if not session_file:
        return
    session = session_loader(work_dir, instance)
    if not session:
        return
    session_id = session_id_extractor(path)
    try:
        session.update_codex_log_binding(log_path=str(path), session_id=session_id)
    except Exception:
        return


def ensure_codex_watchdog_started(
    *,
    has_watchdog: bool,
    started: bool,
    lock,
    session_root: Path,
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
        if not session_root.exists():
            return watcher, started
        instance = watcher_factory(session_root, event_handler, recursive=True)
        try:
            instance.start()
        except Exception:
            return watcher, started
        return instance, True
