from __future__ import annotations

import threading
import time
from pathlib import Path

AUTO_TRANSFER_LOCK = threading.Lock()
AUTO_TRANSFER_SEEN: dict[str, float] = {}


def auto_transfer_key(work_dir: Path, session_path: Path) -> str:
    return f"{work_dir}::{session_path}"


def claim_auto_transfer(key: str, *, now: float | None = None, ttl_s: float = 3600.0) -> bool:
    current_time = time.time() if now is None else now
    with AUTO_TRANSFER_LOCK:
        if key in AUTO_TRANSFER_SEEN:
            return False
        expire_old_entries(now=current_time, ttl_s=ttl_s)
        AUTO_TRANSFER_SEEN[key] = current_time
    return True


def expire_old_entries(*, now: float, ttl_s: float) -> None:
    for existing_key, ts in list(AUTO_TRANSFER_SEEN.items()):
        if now - ts > ttl_s:
            AUTO_TRANSFER_SEEN.pop(existing_key, None)


__all__ = ['AUTO_TRANSFER_SEEN', 'auto_transfer_key', 'claim_auto_transfer', 'expire_old_entries']
