from __future__ import annotations

import os


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    value = raw.strip().lower()
    if value in ("0", "false", "no", "off"):
        return False
    if value in ("1", "true", "yes", "on"):
        return True
    return default


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw.strip())
    except (ValueError, TypeError):
        return default


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw.strip())
    except (ValueError, TypeError):
        return default


__all__ = ['env_bool', 'env_float', 'env_int']
