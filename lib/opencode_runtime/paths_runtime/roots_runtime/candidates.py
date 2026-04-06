from __future__ import annotations

import os
from pathlib import Path


def storage_root_candidates(*, env: dict[str, str], is_wsl_fn) -> list[Path]:
    env_root = (env.get("OPENCODE_STORAGE_ROOT") or "").strip()
    if env_root:
        return [Path(env_root).expanduser()]

    candidates: list[Path] = []
    xdg_data_home = (env.get("XDG_DATA_HOME") or "").strip()
    if xdg_data_home:
        candidates.append(Path(xdg_data_home) / "opencode" / "storage")
    candidates.append(Path.home() / ".local" / "share" / "opencode" / "storage")
    candidates.extend(windows_storage_candidates(env))
    if is_wsl_fn():
        prepend_wsl_storage_candidates(candidates, env=env)
    return candidates


def windows_storage_candidates(env: dict[str, str]) -> list[Path]:
    candidates: list[Path] = []
    localappdata = env.get("LOCALAPPDATA")
    if localappdata:
        candidates.append(Path(localappdata) / "opencode" / "storage")
    appdata = env.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "opencode" / "storage")
    candidates.append(Path.home() / "AppData" / "Local" / "opencode" / "storage")
    candidates.append(Path.home() / "AppData" / "Roaming" / "opencode" / "storage")
    return candidates


def prepend_wsl_storage_candidates(candidates: list[Path], *, env: dict[str, str]) -> None:
    users_root = Path("/mnt/c/Users")
    if not users_root.exists():
        return
    append_preferred_wsl_users(candidates, users_root=users_root, env=env)
    latest = latest_existing_wsl_storage(users_root)
    if latest is not None:
        candidates.insert(0, latest)


def append_preferred_wsl_users(candidates: list[Path], *, users_root: Path, env: dict[str, str]) -> None:
    preferred_names: list[str] = []
    for key in ("WINUSER", "USERNAME", "USER"):
        value = (env.get(key) or "").strip()
        if value and value not in preferred_names:
            preferred_names.append(value)
    for name in preferred_names:
        candidates.append(users_root / name / "AppData" / "Local" / "opencode" / "storage")
        candidates.append(users_root / name / "AppData" / "Roaming" / "opencode" / "storage")


def latest_existing_wsl_storage(users_root: Path) -> Path | None:
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
        return None
    if not found:
        return None
    found.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0.0, reverse=True)
    return found[0]


def log_root_candidates(*, env: dict[str, str]) -> list[Path]:
    env_root = (env.get("OPENCODE_LOG_ROOT") or "").strip()
    if env_root:
        return [Path(env_root).expanduser()]
    candidates: list[Path] = []
    xdg_data_home = (env.get("XDG_DATA_HOME") or "").strip()
    if xdg_data_home:
        candidates.append(Path(xdg_data_home) / "opencode" / "log")
    candidates.append(Path.home() / ".local" / "share" / "opencode" / "log")
    candidates.append(Path.home() / ".opencode" / "log")
    return candidates


__all__ = [
    'append_preferred_wsl_users',
    'latest_existing_wsl_storage',
    'log_root_candidates',
    'prepend_wsl_storage_candidates',
    'storage_root_candidates',
    'windows_storage_candidates',
]
