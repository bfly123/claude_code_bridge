from __future__ import annotations

import os
from pathlib import Path

from .matching import is_wsl


def default_opencode_storage_root() -> Path:
    env = (os.environ.get("OPENCODE_STORAGE_ROOT") or "").strip()
    if env:
        return Path(env).expanduser()

    candidates: list[Path] = []
    xdg_data_home = (os.environ.get("XDG_DATA_HOME") or "").strip()
    if xdg_data_home:
        candidates.append(Path(xdg_data_home) / "opencode" / "storage")
    candidates.append(Path.home() / ".local" / "share" / "opencode" / "storage")

    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        candidates.append(Path(localappdata) / "opencode" / "storage")
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "opencode" / "storage")
    candidates.append(Path.home() / "AppData" / "Local" / "opencode" / "storage")
    candidates.append(Path.home() / "AppData" / "Roaming" / "opencode" / "storage")

    if is_wsl():
        users_root = Path("/mnt/c/Users")
        if users_root.exists():
            preferred_names: list[str] = []
            for key in ("WINUSER", "USERNAME", "USER"):
                value = (os.environ.get(key) or "").strip()
                if value and value not in preferred_names:
                    preferred_names.append(value)
            for name in preferred_names:
                candidates.append(users_root / name / "AppData" / "Local" / "opencode" / "storage")
                candidates.append(users_root / name / "AppData" / "Roaming" / "opencode" / "storage")

            found: list[Path] = []
            try:
                for user_dir in users_root.iterdir():
                    if not user_dir.is_dir():
                        continue
                    for path in (
                        user_dir / "AppData" / "Local" / "opencode" / "storage",
                        user_dir / "AppData" / "Roaming" / "opencode" / "storage",
                    ):
                        if path.exists():
                            found.append(path)
            except Exception:
                found = []
            if found:
                found.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0.0, reverse=True)
                candidates.insert(0, found[0])

    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except Exception:
            continue

    return candidates[0]


def default_opencode_log_root() -> Path:
    env = (os.environ.get("OPENCODE_LOG_ROOT") or "").strip()
    if env:
        return Path(env).expanduser()

    candidates: list[Path] = []
    xdg_data_home = (os.environ.get("XDG_DATA_HOME") or "").strip()
    if xdg_data_home:
        candidates.append(Path(xdg_data_home) / "opencode" / "log")
    candidates.append(Path.home() / ".local" / "share" / "opencode" / "log")
    candidates.append(Path.home() / ".opencode" / "log")

    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except Exception:
            continue

    return candidates[0]


OPENCODE_STORAGE_ROOT = default_opencode_storage_root()
OPENCODE_LOG_ROOT = default_opencode_log_root()


__all__ = [
    "OPENCODE_LOG_ROOT",
    "OPENCODE_STORAGE_ROOT",
    "default_opencode_log_root",
    "default_opencode_storage_root",
]
