from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path


@contextmanager
def file_lock(path: Path):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('a+', encoding='utf-8') as handle:
        try:
            import fcntl  # type: ignore

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except ModuleNotFoundError:
            yield
