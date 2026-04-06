from __future__ import annotations

import os
import threading
from pathlib import Path

from runtime_env import env_bool, env_int

from .state import auto_transfer_key, claim_auto_transfer


def maybe_auto_extract_old_session(old_session_path: str, work_dir: Path) -> None:
    if not env_bool("CCB_CTX_TRANSFER_ON_SESSION_SWITCH", True):
        return
    session_path = normalize_session_path(old_session_path)
    normalized_work_dir = normalize_work_dir(work_dir)
    if session_path is None or normalized_work_dir is None:
        return
    key = auto_transfer_key(normalized_work_dir, session_path)
    if not claim_auto_transfer(key):
        return
    threading.Thread(
        target=lambda: run_auto_transfer(session_path=session_path, work_dir=normalized_work_dir),
        daemon=True,
    ).start()


def normalize_session_path(old_session_path: str) -> Path | None:
    if not old_session_path:
        return None
    try:
        path = Path(old_session_path).expanduser()
    except Exception:
        return None
    if not path.exists():
        return None
    return path


def normalize_work_dir(work_dir: Path) -> Path | None:
    try:
        return Path(work_dir).expanduser()
    except Exception:
        return None


def run_auto_transfer(*, session_path: Path, work_dir: Path) -> None:
    try:
        from memory import ContextTransfer
    except Exception:
        return
    last_n, max_tokens, fmt, provider = transfer_settings()
    try:
        transfer = ContextTransfer(max_tokens=max_tokens, work_dir=work_dir)
        context = transfer.extract_conversations(session_path=session_path, last_n=last_n)
        if not context.conversations:
            return
        filename = build_transfer_filename(session_path)
        transfer.save_transfer(context, fmt, provider, filename=filename)
    except Exception:
        return


def transfer_settings() -> tuple[int, int, str, str]:
    try:
        last_n = env_int("CCB_CTX_TRANSFER_LAST_N", 0)
        max_tokens = env_int("CCB_CTX_TRANSFER_MAX_TOKENS", 8000)
        fmt = (os.environ.get("CCB_CTX_TRANSFER_FORMAT") or "markdown").strip().lower() or "markdown"
        provider = (os.environ.get("CCB_CTX_TRANSFER_PROVIDER") or "auto").strip().lower() or "auto"
        return last_n, max_tokens, fmt, provider
    except Exception:
        return 3, 8000, "markdown", "auto"


def build_transfer_filename(session_path: Path) -> str:
    import time

    ts = time.strftime("%Y%m%d-%H%M%S")
    return f"claude-{ts}-{session_path.stem}"


__all__ = [
    'build_transfer_filename',
    'maybe_auto_extract_old_session',
    'normalize_session_path',
    'normalize_work_dir',
    'run_auto_transfer',
    'transfer_settings',
]
