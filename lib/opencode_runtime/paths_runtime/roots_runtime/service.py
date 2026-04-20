from __future__ import annotations

import os
from pathlib import Path

from ..matching import is_wsl
from .candidates import log_root_candidates, storage_root_candidates


def default_opencode_storage_root() -> Path:
    return first_existing_path(storage_root_candidates(env=os.environ, is_wsl_fn=is_wsl))


def default_opencode_log_root() -> Path:
    return first_existing_path(log_root_candidates(env=os.environ))


def first_existing_path(candidates: list[Path]) -> Path:
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
    'OPENCODE_LOG_ROOT',
    'OPENCODE_STORAGE_ROOT',
    'default_opencode_log_root',
    'default_opencode_storage_root',
    'first_existing_path',
]
