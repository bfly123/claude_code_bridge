from __future__ import annotations

from pathlib import Path
from typing import Callable


def project_dirs_for_work_dir(
    registry,
    work_dir: Path,
    *,
    candidate_project_dirs_fn: Callable[[Path, Path], list[Path]],
    include_missing: bool = False,
) -> list[Path]:
    dirs: list[Path] = []
    for candidate in candidate_project_dirs_fn(registry._claude_root, work_dir):
        if include_missing or candidate.exists():
            dirs.append(candidate)
    return dirs


def ensure_watchers_for_work_dir(
    registry,
    work_dir: Path,
    key: str,
    *,
    has_watchdog: bool,
    watcher_factory,
    candidate_project_dirs_fn: Callable[[Path, Path], list[Path]],
) -> None:
    if not has_watchdog:
        return
    for project_dir in project_dirs_for_work_dir(
        registry,
        work_dir,
        candidate_project_dirs_fn=candidate_project_dirs_fn,
    ):
        project_key = str(project_dir)
        with registry._lock:
            existing = registry._watchers.get(project_key)
            if existing:
                existing.keys.add(key)
                continue
            watcher = watcher_factory(
                project_dir,
                callback=lambda path, project_key=project_key: registry._on_new_log_file(project_key, path),
            )
            registry._watchers[project_key] = registry._watcher_entry_cls(watcher=watcher, keys={key})
        try:
            watcher.start()
        except Exception:
            with registry._lock:
                registry._watchers.pop(project_key, None)


def release_watchers_for_work_dir(
    registry,
    work_dir: Path,
    key: str,
    *,
    has_watchdog: bool,
    candidate_project_dirs_fn: Callable[[Path, Path], list[Path]],
) -> None:
    if not has_watchdog:
        return
    for project_dir in project_dirs_for_work_dir(
        registry,
        work_dir,
        candidate_project_dirs_fn=candidate_project_dirs_fn,
        include_missing=True,
    ):
        project_key = str(project_dir)
        watcher = None
        with registry._lock:
            entry = registry._watchers.get(project_key)
            if not entry:
                continue
            entry.keys.discard(key)
            if entry.keys:
                continue
            watcher = entry.watcher
            registry._watchers.pop(project_key, None)
        if watcher:
            try:
                watcher.stop()
            except Exception:
                pass


def stop_all_watchers(registry, *, has_watchdog: bool) -> None:
    if not has_watchdog:
        return
    with registry._lock:
        entries = list(registry._watchers.values())
        registry._watchers.clear()
    for entry in entries:
        try:
            entry.watcher.stop()
        except Exception:
            pass


def start_root_watcher(registry, *, has_watchdog: bool, watcher_factory) -> None:
    if not has_watchdog:
        return
    if registry._root_watcher is not None:
        return
    root = Path(registry._claude_root).expanduser()
    if not root.exists():
        return
    watcher = watcher_factory(root, callback=registry._on_new_log_file_global, recursive=True)
    registry._root_watcher = watcher
    try:
        watcher.start()
    except Exception:
        registry._root_watcher = None


def stop_root_watcher(registry) -> None:
    watcher = registry._root_watcher
    registry._root_watcher = None
    if not watcher:
        return
    try:
        watcher.stop()
    except Exception:
        pass


__all__ = [
    "ensure_watchers_for_work_dir",
    "project_dirs_for_work_dir",
    "release_watchers_for_work_dir",
    "start_root_watcher",
    "stop_all_watchers",
    "stop_root_watcher",
]
