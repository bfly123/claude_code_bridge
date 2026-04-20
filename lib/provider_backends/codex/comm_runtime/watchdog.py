from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from provider_backends.codex.session_runtime.follow_policy import codex_session_root_path, has_bound_codex_session


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
    if not _should_accept_watchdog_binding(session, path=path, session_id=session_id):
        return
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


def _should_accept_watchdog_binding(session, *, path: Path, session_id: str | None) -> bool:
    data = getattr(session, "data", None)
    session_root = codex_session_root_path(data)
    if session_root is not None and not _is_within(path, session_root):
        return False
    if not has_bound_codex_session(data):
        return True
    current_path = _normalize_path(getattr(session, "codex_session_path", None))
    incoming_path = _normalize_path(path)
    if current_path is not None and incoming_path is not None and current_path == incoming_path:
        return True
    current_session_id = str(getattr(session, "codex_session_id", "") or "").strip()
    normalized_session_id = str(session_id or "").strip()
    return bool(current_session_id and normalized_session_id and current_session_id == normalized_session_id)


def _normalize_path(value: object) -> Path | None:
    if value is None:
        return None
    try:
        return Path(value).expanduser().resolve()
    except Exception:
        try:
            return Path(value).expanduser()
        except Exception:
            return None


def _is_within(path: Path, root: Path) -> bool:
    normalized_path = _normalize_path(path)
    normalized_root = _normalize_path(root)
    if normalized_path is None or normalized_root is None:
        return False
    try:
        normalized_path.relative_to(normalized_root)
        return True
    except Exception:
        return False
