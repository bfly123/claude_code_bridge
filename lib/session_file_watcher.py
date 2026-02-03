from __future__ import annotations

from pathlib import Path
from typing import Callable

try:
    from watchdog.events import FileSystemEventHandler, FileSystemEvent, FileSystemMovedEvent
    from watchdog.observers import Observer
    HAS_WATCHDOG = True
except Exception:
    FileSystemEventHandler = object  # type: ignore[assignment]
    FileSystemEvent = object  # type: ignore[assignment]
    FileSystemMovedEvent = object  # type: ignore[assignment]
    Observer = None  # type: ignore[assignment]
    HAS_WATCHDOG = False


def _is_log_file(path: Path) -> bool:
    return path.suffix == ".jsonl" and not path.name.startswith(".")


def _is_index_file(path: Path) -> bool:
    return path.name == "sessions-index.json"


def _is_watch_file(path: Path) -> bool:
    return _is_log_file(path) or _is_index_file(path)


class SessionFileHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable[[Path], None]):
        self._callback = callback
        super().__init__()

    def _emit(self, path_value: str | None) -> None:
        if not path_value:
            return
        path = Path(path_value)
        if not _is_watch_file(path):
            return
        try:
            self._callback(path)
        except Exception:
            pass

    def on_created(self, event: FileSystemEvent) -> None:
        if not getattr(event, "is_directory", False):
            self._emit(getattr(event, "src_path", None))

    def on_moved(self, event: FileSystemMovedEvent) -> None:
        if not getattr(event, "is_directory", False):
            self._emit(getattr(event, "dest_path", None))

    def on_modified(self, event: FileSystemEvent) -> None:
        if getattr(event, "is_directory", False):
            return
        path_value = getattr(event, "src_path", None)
        if not path_value:
            return
        path = Path(path_value)
        if _is_index_file(path) or _is_log_file(path):
            self._emit(path_value)


class SessionFileWatcher:
    def __init__(self, project_dir: Path, callback: Callable[[Path], None], *, recursive: bool = False):
        self.project_dir = Path(project_dir)
        self.callback = callback
        self.recursive = bool(recursive)
        self.observer = Observer() if HAS_WATCHDOG else None
        self.handler = SessionFileHandler(callback) if HAS_WATCHDOG else None

    def start(self) -> None:
        if not self.observer or not self.handler:
            return
        self.observer.schedule(self.handler, str(self.project_dir), recursive=self.recursive)
        self.observer.daemon = True
        self.observer.start()

    def stop(self) -> None:
        if not self.observer:
            return
        self.observer.stop()
        self.observer.join(timeout=2.0)
