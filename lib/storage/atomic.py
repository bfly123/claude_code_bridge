from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from threading import Lock
from typing import Any

from storage.locks import file_lock

_PATH_LOCKS: dict[str, Lock] = {}
_PATH_LOCKS_GUARD = Lock()


def _path_lock(target: Path) -> Lock:
    key = str(target.resolve(strict=False)).lower()
    with _PATH_LOCKS_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = Lock()
            _PATH_LOCKS[key] = lock
        return lock


def _lock_path(target: Path) -> Path:
    return target.with_name(f'.{target.name}.lock')


def atomic_write_text(path: Path, text: str, *, encoding: str = 'utf-8') -> None:
    target = Path(path)
    with _path_lock(target):
        with file_lock(_lock_path(target)):
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.tmp', dir=str(target.parent))
            try:
                with os.fdopen(fd, 'w', encoding=encoding) as handle:
                    handle.write(text)
                _replace_with_retry(tmp_name, target)
            finally:
                try:
                    os.unlink(tmp_name)
                except FileNotFoundError:
                    pass


def _replace_with_retry(tmp_name: str, target: Path) -> None:
    deadline = time.time() + 1.0
    while True:
        try:
            os.replace(tmp_name, target)
            return
        except PermissionError:
            if time.time() >= deadline:
                raise
            time.sleep(0.01)


def atomic_write_json(path: Path, payload: Any, *, encoding: str = 'utf-8') -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding=encoding)
