from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from env_utils import env_bool, env_int

_AUTO_TRANSFER_LOCK = threading.Lock()
_AUTO_TRANSFER_SEEN: dict[str, float] = {}


def _auto_transfer_key(work_dir: Path, session_path: Path) -> str:
    return f"{work_dir}::{session_path}"


def maybe_auto_extract_old_session(old_session_path: str, work_dir: Path) -> None:
    if not env_bool("CCB_CTX_TRANSFER_ON_SESSION_SWITCH", True):
        return
    if not old_session_path:
        return
    try:
        path = Path(old_session_path).expanduser()
    except Exception:
        return
    if not path.exists():
        return
    try:
        work_dir = Path(work_dir).expanduser()
    except Exception:
        return

    key = _auto_transfer_key(work_dir, path)
    now = time.time()
    with _AUTO_TRANSFER_LOCK:
        if key in _AUTO_TRANSFER_SEEN:
            return
        for existing_key, ts in list(_AUTO_TRANSFER_SEEN.items()):
            if now - ts > 3600:
                _AUTO_TRANSFER_SEEN.pop(existing_key, None)
        _AUTO_TRANSFER_SEEN[key] = now

    def _run() -> None:
        try:
            from memory import ContextTransfer
        except Exception:
            return
        try:
            last_n = env_int("CCB_CTX_TRANSFER_LAST_N", 0)
            max_tokens = env_int("CCB_CTX_TRANSFER_MAX_TOKENS", 8000)
            fmt = (os.environ.get("CCB_CTX_TRANSFER_FORMAT") or "markdown").strip().lower() or "markdown"
            provider = (os.environ.get("CCB_CTX_TRANSFER_PROVIDER") or "auto").strip().lower() or "auto"
        except Exception:
            last_n = 3
            max_tokens = 8000
            fmt = "markdown"
            provider = "auto"
        try:
            transfer = ContextTransfer(max_tokens=max_tokens, work_dir=work_dir)
            context = transfer.extract_conversations(session_path=path, last_n=last_n)
            if not context.conversations:
                return
            ts = time.strftime("%Y%m%d-%H%M%S")
            filename = f"claude-{ts}-{path.stem}"
            transfer.save_transfer(context, fmt, provider, filename=filename)
        except Exception:
            return

    threading.Thread(target=_run, daemon=True).start()


__all__ = ["maybe_auto_extract_old_session"]
