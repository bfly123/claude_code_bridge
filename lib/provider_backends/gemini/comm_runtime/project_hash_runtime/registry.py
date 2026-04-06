from __future__ import annotations

import json
import time
from pathlib import Path

from project.runtime_paths import project_registry_dir

from .candidates import project_hash_candidates


_HASH_CACHE: dict[str, list[Path]] = {}
_HASH_CACHE_TS = 0.0
_HASH_CACHE_SCOPE = ''


def work_dirs_for_hash(project_hash: str, *, root: Path) -> list[Path]:
    global _HASH_CACHE, _HASH_CACHE_SCOPE, _HASH_CACHE_TS
    now = time.time()
    root_path = Path(root).expanduser()
    scope = str(project_registry_dir(Path.cwd()))
    if scope != _HASH_CACHE_SCOPE or now - _HASH_CACHE_TS > 5.0:
        _HASH_CACHE = {}
        for wd in iter_registry_work_dirs(work_dir=Path.cwd()):
            try:
                hashes = project_hash_candidates(wd, root=root_path)
                for value in hashes:
                    _HASH_CACHE.setdefault(value, []).append(wd)
            except Exception:
                continue
        _HASH_CACHE_SCOPE = scope
        _HASH_CACHE_TS = now
    return _HASH_CACHE.get(project_hash, [])


def iter_registry_work_dirs(*, work_dir: Path | str) -> list[Path]:
    registry_root = project_registry_dir(work_dir)
    if not registry_root.exists():
        return []
    work_dirs: list[Path] = []
    try:
        paths = list(registry_root.glob("ccb-session-*.json"))
    except Exception:
        paths = []
    for path in paths:
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        wd = data.get("work_dir")
        if isinstance(wd, str) and wd.strip():
            try:
                work_dirs.append(Path(wd.strip()).expanduser())
            except Exception:
                continue
    return work_dirs


__all__ = ['work_dirs_for_hash']
