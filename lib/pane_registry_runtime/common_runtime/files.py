from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from project.runtime_paths import project_registry_dir

from .debug import debug


REGISTRY_PREFIX = "ccb-session-"
REGISTRY_SUFFIX = ".json"
REGISTRY_TTL_SECONDS = 7 * 24 * 60 * 60


def registry_dir(work_dir: str | Path | None = None) -> Path:
    return project_registry_dir(Path.cwd() if work_dir is None else work_dir)


def registry_path_for_session(session_id: str, *, work_dir: str | Path | None = None) -> Path:
    return registry_dir(work_dir=work_dir) / f"{REGISTRY_PREFIX}{session_id}{REGISTRY_SUFFIX}"


def iter_registry_files(*, work_dir: str | Path | None = None) -> Iterable[Path]:
    current_dir = registry_dir(work_dir=work_dir)
    if not current_dir.exists():
        return []
    return sorted(current_dir.glob(f"{REGISTRY_PREFIX}*{REGISTRY_SUFFIX}"))


def coerce_updated_at(value: Any, fallback_path: Optional[Path] = None) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed.isdigit():
            try:
                return int(trimmed)
            except ValueError:
                pass
    if fallback_path:
        try:
            return int(fallback_path.stat().st_mtime)
        except OSError:
            return 0
    return 0


def is_stale(updated_at: int, now: Optional[int] = None) -> bool:
    if updated_at <= 0:
        return True
    now_ts = int(time.time()) if now is None else int(now)
    return (now_ts - updated_at) > REGISTRY_TTL_SECONDS


def load_registry_file(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception as exc:
        debug(f"Failed to read registry {path}: {exc}")
    return None


__all__ = [
    "REGISTRY_PREFIX",
    "REGISTRY_SUFFIX",
    "REGISTRY_TTL_SECONDS",
    "coerce_updated_at",
    "is_stale",
    "iter_registry_files",
    "load_registry_file",
    "registry_dir",
    "registry_path_for_session",
]
