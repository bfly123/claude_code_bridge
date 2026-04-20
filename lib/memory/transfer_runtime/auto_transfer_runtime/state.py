from __future__ import annotations

import threading
import time
from pathlib import Path

AUTO_TRANSFER_LOCK = threading.Lock()
AUTO_TRANSFER_SEEN: dict[str, float] = {}


def auto_transfer_key(
    provider: str,
    work_dir: Path,
    session_path: Path | None,
    session_id: str | None,
    project_id: str | None,
) -> str:
    return f"{provider}::{work_dir}::{session_path or ''}::{session_id or ''}::{project_id or ''}"


def claim_auto_transfer(key: str, *, now: float | None = None, ttl_s: float = 3600.0) -> bool:
    now = time.time() if now is None else float(now)
    with AUTO_TRANSFER_LOCK:
        if key in AUTO_TRANSFER_SEEN:
            return False
        for existing_key, ts in list(AUTO_TRANSFER_SEEN.items()):
            if now - ts > ttl_s:
                AUTO_TRANSFER_SEEN.pop(existing_key, None)
        AUTO_TRANSFER_SEEN[key] = now
    return True


__all__ = ['AUTO_TRANSFER_SEEN', 'auto_transfer_key', 'claim_auto_transfer']
