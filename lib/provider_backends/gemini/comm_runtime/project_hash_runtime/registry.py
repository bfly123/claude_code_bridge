from __future__ import annotations

import json
import time
from pathlib import Path

from project.runtime_paths import project_registry_dir

from .candidates import project_hash_candidates


_HASH_CACHE: dict[str, list[Path]] = {}
_HASH_CACHE_TS = 0.0
_HASH_CACHE_SCOPE = ''
_CACHE_TTL_SECONDS = 5.0


def _cache_scope() -> str:
    return str(project_registry_dir(Path.cwd()))


def _should_refresh_cache(*, scope: str, now: float) -> bool:
    return scope != _HASH_CACHE_SCOPE or now - _HASH_CACHE_TS > _CACHE_TTL_SECONDS


def _index_hash_candidates(cache: dict[str, list[Path]], *, work_dir: Path, root: Path) -> None:
    try:
        hashes = project_hash_candidates(work_dir, root=root)
    except Exception:
        return
    for value in hashes:
        cache.setdefault(value, []).append(work_dir)


def _rebuild_hash_cache(*, root: Path) -> None:
    global _HASH_CACHE
    cache: dict[str, list[Path]] = {}
    for work_dir in iter_registry_work_dirs(work_dir=Path.cwd()):
        _index_hash_candidates(cache, work_dir=work_dir, root=root)
    _HASH_CACHE = cache


def _registry_paths(registry_root: Path) -> list[Path]:
    try:
        return list(registry_root.glob("ccb-session-*.json"))
    except Exception:
        return []


def _load_registry_work_dir(path: Path) -> Path | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    wd = data.get("work_dir")
    if not isinstance(wd, str) or not wd.strip():
        return None
    try:
        return Path(wd.strip()).expanduser()
    except Exception:
        return None


def work_dirs_for_hash(project_hash: str, *, root: Path) -> list[Path]:
    global _HASH_CACHE, _HASH_CACHE_SCOPE, _HASH_CACHE_TS
    now = time.time()
    root_path = Path(root).expanduser()
    scope = _cache_scope()
    if _should_refresh_cache(scope=scope, now=now):
        _rebuild_hash_cache(root=root_path)
        _HASH_CACHE_SCOPE = scope
        _HASH_CACHE_TS = now
    return _HASH_CACHE.get(project_hash, [])


def iter_registry_work_dirs(*, work_dir: Path | str) -> list[Path]:
    registry_root = project_registry_dir(work_dir)
    if not registry_root.exists():
        return []
    work_dirs: list[Path] = []
    for path in _registry_paths(registry_root):
        work_dir_path = _load_registry_work_dir(path)
        if work_dir_path is not None:
            work_dirs.append(work_dir_path)
    return work_dirs


__all__ = ['work_dirs_for_hash']
