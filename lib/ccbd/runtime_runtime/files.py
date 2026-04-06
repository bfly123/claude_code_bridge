from __future__ import annotations

import os
from pathlib import Path


def run_dir() -> Path:
    override = (os.environ.get("CCB_RUN_DIR") or "").strip()
    if override:
        return Path(override).expanduser()

    if os.name == "nt":
        base = (os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or "").strip()
        if base:
            return Path(base) / "ccb"
        return Path.home() / "AppData" / "Local" / "ccb"

    xdg_cache = (os.environ.get("XDG_CACHE_HOME") or "").strip()
    if xdg_cache:
        return Path(xdg_cache) / "ccb"
    return Path.home() / ".cache" / "ccb"


def state_file_path(name: str) -> Path:
    if name.endswith(".json"):
        return run_dir() / name
    return run_dir() / f"{name}.json"


def log_path(name: str) -> Path:
    if name.endswith(".log"):
        return run_dir() / name
    return run_dir() / f"{name}.log"


__all__ = ["log_path", "run_dir", "state_file_path"]
